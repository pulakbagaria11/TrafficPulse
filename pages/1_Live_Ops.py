import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label
from src.hotspot import make_heatmap, top_hotspots
from src.tow_truck import make_breakdown_map, preposition_recommendations

st.set_page_config(page_title="Live Ops | TrafficPulse", layout="wide")
st.title("Live Ops Dashboard")

df = load_data()

if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")

    all_causes = sorted(df['event_cause'].dropna().unique().tolist())
    selected_causes = st.multiselect(
        "Event cause",
        options=all_causes,
        default=[],
        format_func=cause_label,
    )

    hour_range = st.slider("Hour of day (IST)", 0, 23, (0, 23))

    view_mode = st.radio("Map view", ["Heatmap", "Breakdown hotspots"])

# --- Apply filters ---
filtered = df.copy()
if selected_causes:
    filtered = filtered[filtered['event_cause'].isin(selected_causes)]
if 'hour' in filtered.columns:
    filtered = filtered[filtered['hour'].between(hour_range[0], hour_range[1])]

# --- Summary metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Incidents", f"{len(filtered):,}")

if 'priority_enc' in filtered.columns:
    col2.metric("High Priority", f"{int(filtered['priority_enc'].sum()):,}")
else:
    col2.metric("High Priority", "N/A")

if 'closure_enc' in filtered.columns:
    col3.metric("Road Closures", f"{int(filtered['closure_enc'].sum()):,}")
else:
    col3.metric("Road Closures", "N/A")

if 'duration_mins' in filtered.columns:
    avg_dur = filtered['duration_mins'].dropna().mean()
    col4.metric("Avg Response (min)", f"{avg_dur:.0f}" if not pd.isna(avg_dur) else "N/A")
else:
    col4.metric("Avg Response (min)", "N/A")

st.markdown("---")

# --- Map ---
map_col, info_col = st.columns([3, 1])

with map_col:
    st.subheader("Incident Map")
    if view_mode == "Heatmap":
        m = make_heatmap(filtered)
    else:
        m = make_breakdown_map(filtered)

    st_folium(m, width=None, height=480, returned_objects=[])

with info_col:
    st.subheader("Top Hotspots")
    grid = top_hotspots(filtered, n=8)
    if not grid.empty:
        for i, row in grid.iterrows():
            st.markdown(
                f"**{row['lat_grid']:.2f}, {row['lon_grid']:.2f}**  \n"
                f"{int(row['incident_count'])} incidents"
            )
    else:
        st.info("No hotspot data for current filter.")

st.markdown("---")

# --- Charts ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Incidents by Cause")
    cause_counts = (
        filtered['event_cause']
        .value_counts()
        .head(8)
        .reset_index()
        .rename(columns={'event_cause': 'cause', 'count': 'count'})
    )
    cause_counts['cause_label'] = cause_counts['cause'].apply(cause_label)
    if not cause_counts.empty:
        fig = px.bar(
            cause_counts,
            x='count',
            y='cause_label',
            orientation='h',
            color_discrete_sequence=['#1a3a5c'],
        )
        fig.update_layout(
            yaxis_title=None, xaxis_title="Incidents",
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.subheader("Incidents by Hour (IST)")
    if 'hour' in filtered.columns:
        hour_counts = filtered['hour'].value_counts().sort_index().reset_index()
        hour_counts.columns = ['hour', 'count']
        fig2 = px.bar(
            hour_counts,
            x='hour',
            y='count',
            color_discrete_sequence=['#1a3a5c'],
        )
        fig2.update_layout(
            xaxis_title="Hour",
            yaxis_title="Incidents",
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
        )
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# --- Tow truck pre-positioning ---
st.subheader("Tow Truck Pre-Positioning")
recs = preposition_recommendations(filtered)
if recs:
    rec_df = pd.DataFrame(recs)
    rec_df = rec_df.rename(columns={
        'lat': 'Latitude',
        'lon': 'Longitude',
        'breakdowns': 'Breakdown Count',
        'deploy_during': 'Deploy During',
        'trucks_recommended': 'Trucks',
    })
    st.dataframe(rec_df, use_container_width=True, hide_index=True)
else:
    st.info("No breakdown data found in current filter.")

# --- Recent events table ---
st.markdown("---")
st.subheader("Recent Incidents")
display_cols = [c for c in [
    'start_datetime', 'event_cause', 'event_type', 'priority',
    'requires_road_closure', 'corridor', 'zone'
] if c in filtered.columns]

recent = filtered.sort_values('start_datetime', ascending=False).head(50) \
    if 'start_datetime' in filtered.columns else filtered.head(50)

st.dataframe(
    recent[display_cols].reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
)
