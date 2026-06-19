import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="TrafficPulse",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    h1, h2, h3 {font-weight: 600;}
    .stMetric label {font-size: 0.8rem; color: #555;}
</style>
""", unsafe_allow_html=True)

st.title("TrafficPulse")
st.caption("Event-Driven Congestion Management — Bengaluru")

st.markdown("---")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    ### About

    TrafficPulse forecasts traffic congestion from both planned and unplanned events,
    recommends field resources, and tracks historical patterns to improve response over time.

    **Built on**: Astram incident dataset, Nov 2023 – Apr 2024 (8,173 events)

    ---

    ### Modules

    | Module | Description |
    |---|---|
    | Live Ops | Incident heatmap, event feed, breakdown hotspots |
    | Prediction Tool | Forecast severity and resource need for any event |
    | Citizen Reports | Public incident reporting with auto-verification |
    | After-Action Report | Predicted vs. actual outcome analysis |
    | Leaderboards | Officer response scores and reporter points |
    | Violation Hotspots | Recurring incident locations with escalation tracking |

    ---

    Navigate using the sidebar.
    """)

with col2:
    data_path = Path("data/events.csv")
    if data_path.exists():
        st.success("Data loaded")
        import pandas as pd
        df = pd.read_csv(data_path)
        st.metric("Total Events", f"{len(df):,}")
    else:
        st.warning("Place events.csv in data/ folder to activate all features.")
