import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label
from src.violation_hotspot import get_violation_hotspots, make_violation_map, escalation_summary

st.set_page_config(page_title="Violation Hotspots | TrafficPulse", layout="wide")
st.markdown("<style>h1,h2,h3{font-weight:600;}.stMetric label{font-size:0.8rem;color:#666;}</style>",
            unsafe_allow_html=True)

st.title("Violation Hotspot Tracker")
st.caption("Locations with 3+ repeat incidents flagged as Recurring. 6+ triggers Escalated status.")

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

# Enrich hotspots with corridor info
def enrich_hotspots(hotspots, df):
    if 'corridor' not in df.columns:
        return hotspots
    enriched = []
    for _, row in hotspots.iterrows():
        nearby = df[
            (df['lat_grid'] == row['lat_grid']) &
            (df['lon_grid'] == row['lon_grid'])
        ]
        corridors = nearby['corridor'].dropna().value_counts()
        junction = nearby['junction'].dropna().value_counts() if 'junction' in nearby.columns else pd.Series()
        row = row.copy()
        row['corridor'] = corridors.index[0] if len(corridors) > 0 else ''
        row['junction'] = junction.index[0] if len(junction) > 0 else ''
        enriched.append(row)
    return pd.DataFrame(enriched)

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")
    min_incidents = st.slider("Minimum incidents", 2, 20, 3)
    status_filter = st.multiselect(
        "Status", options=['Escalated', 'Recurring'],
        default=['Escalated', 'Recurring'],
    )

# --- Summary ---
esc = escalation_summary(df)
if esc:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Hotspots", esc.get('total_hotspots', 0))
    c2.metric("Escalated (6+)", esc.get('escalated', 0))
    c3.metric("Recurring (3-5)", esc.get('recurring', 0))
    c4.metric("Worst Location", esc.get('worst_location', 'N/A'))

st.markdown("---")

hotspots = get_violation_hotspots(df, min_incidents=min_incidents)
hotspots = enrich_hotspots(hotspots, df)
if status_filter:
    hotspots = hotspots[hotspots['status'].isin(status_filter)]

# --- Map + table ---
map_col, table_col = st.columns([3, 2])

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
        display['Location'] = display.apply(
            lambda r: r.get('corridor') or r.get('junction') or
                      f"{r['lat_grid']:.2f}, {r['lon_grid']:.2f}", axis=1
        )
        display['Primary Cause'] = display['top_cause'].fillna('Unknown')
        rename = {
            'incident_count': 'Incidents',
            'status': 'Status',
            'last_seen': 'Last Seen',
        }
        display = display.rename(columns=rename)
        show_cols = ['Location', 'Primary Cause', 'Incidents', 'Status']
        if 'Last Seen' in display.columns:
            show_cols.append('Last Seen')
        st.dataframe(display[show_cols], use_container_width=True, hide_index=True)

st.markdown("---")

# --- Escalated locations detail ---
escalated = hotspots[hotspots['status'] == 'Escalated'] if not hotspots.empty else pd.DataFrame()
st.subheader(f"Escalated Locations ({len(escalated)})")

if escalated.empty:
    st.success("No escalated hotspots under current filter.")
else:
    for _, row in escalated.iterrows():
        location_name = (row.get('corridor') or row.get('junction') or
                         f"{row['lat_grid']:.2f}, {row['lon_grid']:.2f}")
        st.markdown(
            f"""<div style="border-left:4px solid #8e44ad;padding:0.6rem 1rem;
            margin-bottom:0.5rem;background:#f9f0ff;border-radius:4px;">
            <b>{location_name}</b> &nbsp;&mdash;&nbsp;
            {row.get('top_cause', 'Unknown')} &nbsp;&mdash;&nbsp;
            <b>{int(row['incident_count'])} incidents</b>
            </div>""",
            unsafe_allow_html=True,
        )

# --- Escalation report export ---
st.markdown("---")
st.subheader("Generate Escalation Report")
st.caption("Copy or download this report to share with BBMP or the Commissioner's office.")

if not escalated.empty:
    report_lines = [
        "TRAFFICPULSE — ESCALATION REPORT",
        f"Generated: {date.today().strftime('%d %b %Y')}",
        f"Dataset: Astram incidents, Nov 2023 – Apr 2024",
        "",
        f"ESCALATED LOCATIONS — {len(escalated)} locations with 6 or more repeat incidents",
        "=" * 60,
    ]
    for i, row in escalated.reset_index(drop=True).iterrows():
        location_name = (row.get('corridor') or row.get('junction') or
                         f"Grid {row['lat_grid']:.2f}, {row['lon_grid']:.2f}")
        report_lines.append(
            f"\n{i+1}. {location_name}\n"
            f"   Incidents: {int(row['incident_count'])}\n"
            f"   Primary cause: {row.get('top_cause', 'Unknown')}\n"
            f"   Recommended action: Infrastructure review and preventive deployment"
        )

    report_lines += [
        "\n" + "=" * 60,
        "\nRECURRING LOCATIONS (3-5 incidents)",
        "=" * 60,
    ]
    recurring = hotspots[hotspots['status'] == 'Recurring']
    for i, row in recurring.reset_index(drop=True).iterrows():
        location_name = (row.get('corridor') or row.get('junction') or
                         f"Grid {row['lat_grid']:.2f}, {row['lon_grid']:.2f}")
        report_lines.append(f"{i+1}. {location_name} — {int(row['incident_count'])} incidents")

    report_text = "\n".join(report_lines)

    st.download_button(
        label="Download Escalation Report (.txt)",
        data=report_text,
        file_name=f"trafficpulse_escalation_{date.today().isoformat()}.txt",
        mime="text/plain",
    )

    with st.expander("Preview report"):
        st.text(report_text)
else:
    st.info("No escalated hotspots to report under current filter.")
