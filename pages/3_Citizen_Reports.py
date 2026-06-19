import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
from streamlit_folium import st_folium
import folium

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, BENGALURU_CENTER
from src.reporter_score import submit_report, get_all_reports, init_reports

st.set_page_config(page_title="Citizen Reports | TrafficPulse", layout="wide")
st.title("Citizen Reports")
st.caption("Submit and track public incident reports. 3 or more reports in the same area trigger auto-verification.")

init_reports()

df = load_data()

# --- VIP Alert panel ---
if df is not None and 'event_cause' in df.columns:
    vip_events = df[df['event_cause'] == 'vip_movement']
    if not vip_events.empty:
        latest_vip = vip_events.sort_values('start_datetime', ascending=False).iloc[0]
        corridor = str(latest_vip.get('corridor', 'City centre')).strip()
        with st.container():
            st.markdown(
                f"""
                <div style="background:#1a3a5c;color:white;padding:0.8rem 1rem;
                            border-radius:6px;margin-bottom:1rem;">
                    <b>VIP Movement Alert</b> &nbsp;&mdash;&nbsp;
                    Corridor: {corridor} &nbsp;|&nbsp;
                    Expect delays. Plan alternate routes.
                </div>
                """,
                unsafe_allow_html=True,
            )

# --- Report form ---
left, right = st.columns([1, 1])

with left:
    st.subheader("Submit a Report")
    with st.form("report_form", clear_on_submit=True):
        reporter_id = st.text_input("Your ID (optional)", placeholder="e.g. CIT1234")
        cause = st.selectbox(
            "Incident type",
            options=[
                'vehicle_breakdown', 'accident', 'pot_holes',
                'water_logging', 'construction', 'tree_fall',
                'procession', 'other',
            ],
            format_func=lambda x: x.replace('_', ' ').title(),
        )
        lat = st.number_input("Latitude", value=12.9716, format="%.4f")
        lon = st.number_input("Longitude", value=77.5946, format="%.4f")
        desc = st.text_area("Description (optional)", max_chars=200)
        submitted = st.form_submit_button("Submit Report")

    if submitted:
        rid = reporter_id.strip() or f"ANON_{len(get_all_reports()) + 1}"
        idx = submit_report(rid, cause, lat, lon, desc)
        reports = get_all_reports()
        report = reports.iloc[idx]
        if report.get('verified'):
            st.success("Report submitted and auto-verified (3+ reports in this area).")
        else:
            st.success("Report submitted. Awaiting verification from nearby reports.")

with right:
    st.subheader("Report Map")
    m = folium.Map(location=BENGALURU_CENTER, zoom_start=11, tiles='CartoDB positron')

    reports_df = get_all_reports()
    if not reports_df.empty:
        for _, row in reports_df.iterrows():
            color = 'green' if row.get('verified') else 'gray'
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=7,
                color=color,
                fill=True,
                fill_opacity=0.75,
                popup=folium.Popup(
                    f"<b>{str(row['cause']).replace('_',' ').title()}</b><br>"
                    f"{'Verified' if row.get('verified') else 'Pending'}",
                    max_width=180,
                ),
            ).add_to(m)
    else:
        if df is not None:
            sample = df.sample(min(30, len(df)), random_state=42)
            for _, row in sample.iterrows():
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=4,
                    color='#aaa',
                    fill=True,
                    fill_opacity=0.5,
                    tooltip="Historical incident",
                ).add_to(m)

    st_folium(m, width=None, height=360, returned_objects=[])

# --- Live feed ---
st.markdown("---")
st.subheader("Report Feed")

reports_df = get_all_reports()
if not reports_df.empty:
    display = reports_df.copy()
    display['status'] = display['verified'].apply(lambda v: 'Verified' if v else 'Pending')
    display['cause'] = display['cause'].apply(lambda x: x.replace('_', ' ').title())
    st.dataframe(
        display[['reporter_id', 'cause', 'lat', 'lon', 'status', 'points_awarded']],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No reports submitted yet in this session. Submit one above to see the feed.")
    st.caption("In a live deployment, this feed would show real-time incoming reports from the public.")
