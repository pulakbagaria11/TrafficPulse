import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label
from src.violation_hotspot import (
    get_violation_hotspots, make_violation_map, escalation_summary
)

st.set_page_config(page_title="Violation Hotspots | TrafficPulse", layout="wide")
st.title("Violation Hotspot Tracker")
st.caption(
    "Locations with 3 or more repeat incidents are flagged as Recurring. "
    "6 or more triggers Escalated status for senior review."
)

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

# --- Summary ---
esc = escalation_summary(df)
if esc:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Hotspots", esc.get('total_hotspots', 0))
    c2.metric("Escalated", esc.get('escalated', 0))
    c3.metric("Recurring", esc.get('recurring', 0))
    c4.metric("Worst Location", esc.get('worst_location', 'N/A'))

st.markdown("---")

# --- Filters ---
with st.sidebar:
    st.header("Filters")
    min_incidents = st.slider("Minimum incidents", 2, 20, 3)
    status_filter = st.multiselect(
        "Status",
        options=['Escalated', 'Recurring'],
        default=['Escalated', 'Recurring'],
    )

# --- Map + table ---
map_col, table_col = st.columns([3, 2])

hotspots = get_violation_hotspots(df, min_incidents=min_incidents)
if status_filter:
    hotspots = hotspots[hotspots['status'].isin(status_filter)]

with map_col:
    st.subheader("Hotspot Map")
    m = make_violation_map(df)
    st_folium(m, width=None, height=460, returned_objects=[])

with table_col:
    st.subheader("Hotspot Table")
    if hotspots.empty:
        st.info("No hotspots match the current filter.")
    else:
        display = hotspots.copy()
        display['top_cause'] = display['top_cause'].fillna('Unknown')
        rename = {
            'lat_grid': 'Latitude',
            'lon_grid': 'Longitude',
            'incident_count': 'Incidents',
            'top_cause': 'Primary Cause',
            'status': 'Status',
            'last_seen': 'Last Seen',
            'high_priority': 'High Priority',
        }
        display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})
        show_cols = [v for v in rename.values() if v in display.columns]
        st.dataframe(display[show_cols], use_container_width=True, hide_index=True)

st.markdown("---")

# --- Escalation details ---
escalated = hotspots[hotspots['status'] == 'Escalated'] if not hotspots.empty else pd.DataFrame()

st.subheader("Escalated Locations")
if escalated.empty:
    st.success("No escalated hotspots under current filter.")
else:
    for _, row in escalated.iterrows():
        with st.container():
            st.markdown(
                f"""
                <div style="border-left:4px solid #8e44ad;padding:0.6rem 1rem;
                            margin-bottom:0.5rem;background:#f9f0ff;border-radius:4px;">
                    <b>{row['lat_grid']:.2f}, {row['lon_grid']:.2f}</b> &nbsp;&mdash;&nbsp;
                    {row.get('top_cause', 'Unknown')} &nbsp;&mdash;&nbsp;
                    <b>{int(row['incident_count'])} incidents</b>
                    {' &nbsp;| Last seen: ' + str(row.get('last_seen', '')) if 'last_seen' in row else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("---")

# --- Trend chart ---
st.subheader("Incident Count Distribution")
if not hotspots.empty:
    fig = px.histogram(
        hotspots,
        x='incident_count',
        color='status',
        nbins=20,
        color_discrete_map={'Escalated': '#8e44ad', 'Recurring': '#e67e22'},
        labels={'incident_count': 'Incidents per Location', 'count': 'Locations'},
    )
    fig.update_layout(
        bargap=0.1,
        margin=dict(l=0, r=0, t=10, b=0),
        height=250,
    )
    st.plotly_chart(fig, use_container_width=True)
