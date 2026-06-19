import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label
from src.hotspot import make_heatmap, make_marker_map, top_hotspots
from src.tow_truck import make_breakdown_map, preposition_recommendations
from src.corridor import get_corridor_stats
from src.reporter_score import get_all_reports, init_reports
from src.flood_risk import get_flood_prone_locations, make_flood_map
from src.cascade import compute_cascade_risk
from src.live_replay import initial_cursor, make_replay_map, replay_counts, STEP_OPTIONS
import folium

st.set_page_config(page_title="Live Ops | TrafficPulse", layout="wide")
st.markdown("""
<style>
h1,h2,h3{font-weight:600;}
.stMetric label{font-size:0.8rem;color:#666;}
.status-badge{display:inline-block;padding:2px 8px;border-radius:3px;font-size:0.78rem;font-weight:600;}
</style>
""", unsafe_allow_html=True)

st.title("Live Ops Dashboard")
init_reports()

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")

    all_causes = sorted(df['event_cause'].dropna().unique().tolist())
    selected_causes = st.multiselect(
        "Event cause", options=all_causes, default=[],
        format_func=cause_label,
    )

    if 'month' in df.columns:
        month_names = {11: 'Nov 2023', 12: 'Dec 2023', 1: 'Jan 2024',
                       2: 'Feb 2024', 3: 'Mar 2024', 4: 'Apr 2024'}
        available_months = sorted(df['month'].dropna().unique().tolist())
        selected_months = st.multiselect(
            "Month", options=available_months,
            format_func=lambda m: month_names.get(int(m), str(m)),
            default=[],
        )

    if 'weekday' in df.columns:
        day_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday',
                     3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
        selected_days = st.multiselect(
            "Day of week", options=list(range(7)),
            format_func=lambda d: day_names[d], default=[],
        )

    event_type_filter = st.radio(
        "Event type", options=["All", "Planned", "Unplanned"],
    )

    hour_range = st.slider("Hour of day (IST)", 0, 23, (0, 23))

    view_mode = st.radio("Map view", ["Heatmap", "Breakdown hotspots", "Live Replay"])

# --- Apply filters ---
filtered = df.copy()
if selected_causes:
    filtered = filtered[filtered['event_cause'].isin(selected_causes)]
if 'month' in filtered.columns and selected_months:
    filtered = filtered[filtered['month'].isin(selected_months)]
if 'weekday' in filtered.columns and selected_days:
    filtered = filtered[filtered['weekday'].isin(selected_days)]
if event_type_filter != "All" and 'event_type' in filtered.columns:
    filtered = filtered[filtered['event_type'] == event_type_filter.lower()]
if 'hour' in filtered.columns:
    filtered = filtered[filtered['hour'].between(hour_range[0], hour_range[1])]

# --- Metrics ---
total = len(filtered)
high = int(filtered['priority_enc'].sum()) if 'priority_enc' in filtered.columns else 0
closures = int(filtered['closure_enc'].sum()) if 'closure_enc' in filtered.columns else 0
planned = int((filtered['event_type'] == 'planned').sum()) if 'event_type' in filtered.columns else 0
unplanned = total - planned
avg_dur = filtered['duration_mins'].dropna().mean() if 'duration_mins' in filtered.columns else None

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Incidents", f"{total:,}")
c2.metric("High Priority", f"{high:,}", f"{high/total*100:.0f}%" if total else "")
c3.metric("Road Closures", f"{closures:,}")
c4.metric("Planned / Unplanned", f"{planned} / {unplanned}")
c5.metric("Avg Response (min)", f"{avg_dur:.0f}" if avg_dur and not pd.isna(avg_dur) else "N/A")

st.markdown("---")

# --- Map ---
map_col, side_col = st.columns([3, 1])

with map_col:
    st.subheader("Incident Map")
    reports_df = get_all_reports()

    if view_mode == "Heatmap":
        m = make_heatmap(filtered)
    elif view_mode == "Breakdown hotspots":
        m = make_breakdown_map(filtered)
    else:
        st.caption(
            "Replays the full Astram history in timestamp order to simulate a live incident "
            "feed -- independent of the filters above, since chronological order matters here."
        )
        if 'replay_cursor' not in st.session_state:
            st.session_state['replay_cursor'] = initial_cursor(df)

        step_label = st.select_slider("Step size", options=list(STEP_OPTIONS.keys()), value='1 day')

        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            if st.button("Step Forward", use_container_width=True):
                st.session_state['replay_cursor'] = min(
                    st.session_state['replay_cursor'] + STEP_OPTIONS[step_label],
                    df['start_datetime'].max(),
                )
        with rc2:
            if st.button("Reset to Start", use_container_width=True):
                st.session_state['replay_cursor'] = initial_cursor(df)
        with rc3:
            if st.button("Jump to End", use_container_width=True):
                st.session_state['replay_cursor'] = df['start_datetime'].max()

        cursor = st.session_state['replay_cursor']
        cumulative_count, recent_count = replay_counts(df, cursor, step_label)

        rm1, rm2, rm3 = st.columns(3)
        rm1.metric("Simulated Clock", cursor.strftime('%d %b %Y, %H:%M'))
        rm2.metric("Incidents Received", f"{cumulative_count:,}")
        rm3.metric(f"New ({step_label})", f"+{recent_count}")

        m = make_replay_map(df, cursor, step_label)

    # Overlay citizen reports
    if not reports_df.empty:
        for _, r in reports_df.iterrows():
            color = '#27ae60' if r.get('verified') else '#f39c12'
            folium.CircleMarker(
                location=[r['lat'], r['lon']],
                radius=8, color=color, fill=True, fill_opacity=0.9,
                tooltip=f"Citizen report: {str(r['cause']).replace('_',' ').title()} "
                        f"({'Verified' if r.get('verified') else 'Pending'})",
            ).add_to(m)

    st_folium(m, width=None, height=500, returned_objects=[])

    if view_mode == "Live Replay":
        st.caption("Heatmap: cumulative incidents up to the simulated clock. Red markers: incidents that just arrived this step.")
    elif not reports_df.empty:
        st.caption(
            f"Green: verified citizen reports ({int(reports_df['verified'].sum())})   "
            f"Orange: pending ({int((~reports_df['verified']).sum())})"
        )

with side_col:
    st.subheader("Top Hotspots")
    grid = top_hotspots(filtered, n=8)
    if not grid.empty:
        for _, row in grid.iterrows():
            st.markdown(
                f"**{row['lat_grid']:.2f}, {row['lon_grid']:.2f}**  \n"
                f"{int(row['incident_count'])} incidents"
            )
    else:
        st.info("No hotspots in current filter.")

    st.markdown("---")
    st.subheader("Event Breakdown")
    if 'event_cause' in filtered.columns:
        top5 = filtered['event_cause'].value_counts().head(5)
        for cause, count in top5.items():
            pct = count / total * 100 if total else 0
            st.markdown(f"**{cause_label(cause)}** — {count:,} ({pct:.0f}%)")

st.markdown("---")

# --- Charts ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Incidents by Hour (IST)")
    if 'hour' in filtered.columns:
        hc = filtered['hour'].value_counts().sort_index().reset_index()
        hc.columns = ['hour', 'count']
        fig = px.bar(hc, x='hour', y='count', color_discrete_sequence=['#1a3a5c'])
        fig.update_layout(
            xaxis_title="Hour", yaxis_title="Incidents",
            margin=dict(l=0, r=0, t=10, b=0), height=260,
        )
        st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.subheader("Incidents by Day of Week")
    if 'weekday' in filtered.columns:
        day_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
        dc = filtered.groupby('weekday').size().reset_index(name='count')
        dc['day'] = dc['weekday'].map(day_map)
        fig2 = px.bar(dc, x='day', y='count', color_discrete_sequence=['#1a3a5c'])
        fig2.update_layout(
            xaxis_title=None, yaxis_title="Incidents",
            margin=dict(l=0, r=0, t=10, b=0), height=260,
        )
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# --- Corridor analysis ---
st.subheader("Corridor Risk Summary")
corridor_stats = get_corridor_stats(filtered, top_n=10)
if not corridor_stats.empty:
    display_cs = corridor_stats.copy()
    rename_map = {
        'corridor': 'Corridor',
        'incidents': 'Incidents',
        'high_priority_rate_pct': 'High Priority %',
        'closure_rate_pct': 'Closure %',
        'avg_duration_mins': 'Avg Duration (min)',
    }
    display_cs = display_cs.rename(columns={k: v for k, v in rename_map.items() if k in display_cs.columns})
    show_cols = [v for v in rename_map.values() if v in display_cs.columns]
    st.dataframe(display_cs[show_cols], use_container_width=True, hide_index=True)
else:
    st.info("No corridor data available for current filter.")

st.markdown("---")

# --- Tow truck pre-positioning ---
st.subheader("Tow Truck Pre-Positioning")
st.caption("Derived from breakdown hotspot clustering. Trucks recommended for pre-deployment before peak periods.")
recs = preposition_recommendations(filtered)
if recs:
    rc1, rc2 = st.columns(2)
    for i, r in enumerate(recs[:6]):
        col = rc1 if i % 2 == 0 else rc2
        with col:
            st.markdown(
                f"**Location {i+1}** — {r['lat']:.2f}, {r['lon']:.2f}  \n"
                f"{r['breakdowns']} breakdowns — deploy {r['trucks_recommended']} truck(s) — {r['deploy_during']}"
            )
else:
    st.info("No breakdown data found in current filter.")

st.markdown("---")

# --- Flood-prone roads ---
st.subheader("Flood-Prone Roads")
st.caption("Locations with 2+ historical water-logging incidents.")
flood_col, flood_list_col = st.columns([3, 1])
flood_locations = get_flood_prone_locations(filtered)
with flood_col:
    if not flood_locations.empty:
        st_folium(make_flood_map(filtered), width=None, height=380, returned_objects=[])
    else:
        st.info("No water-logging hotspots in current filter.")
with flood_list_col:
    for _, row in flood_locations.head(6).iterrows():
        location_label = row.get('corridor') or f"{row['lat_grid']:.2f}, {row['lon_grid']:.2f}"
        st.markdown(
            f"**{location_label}**  \n"
            f"{int(row['incident_count'])} incidents"
        )

st.markdown("---")

# --- Cascade risk ---
st.subheader("Cascade Risk")
st.caption("Historical likelihood that an incident on a corridor is followed by one on an adjacent corridor within 3 hours, versus that corridor's baseline rate.")
cascade = compute_cascade_risk(df)
if not cascade.empty:
    top_cascade = cascade.head(8).copy()
    top_cascade['Pair'] = top_cascade['corridor'] + ' -> ' + top_cascade['alt_corridor']
    display_cols = top_cascade.rename(columns={
        'cascade_rate_pct': 'Cascade Rate %',
        'baseline_rate_pct': 'Baseline Rate %',
        'uplift_x': 'Uplift (x)',
    })[['Pair', 'Cascade Rate %', 'Baseline Rate %', 'Uplift (x)']]
    st.dataframe(display_cols, use_container_width=True, hide_index=True)
else:
    st.info("Not enough data to compute cascade risk for current corridors.")
