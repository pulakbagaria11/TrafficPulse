import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="TrafficPulse",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebarNav"] ul {padding-top: 0.5rem;}
    h1, h2, h3 {font-weight: 600;}
    .stMetric label {font-size: 0.8rem; color: #666;}
    .module-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-left: 4px solid #1a3a5c;
        border-radius: 4px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.6rem;
    }
    .module-card h4 {margin: 0 0 0.3rem 0; font-size: 0.95rem; color: #1a3a5c;}
    .module-card p {margin: 0; font-size: 0.82rem; color: #555;}
    .pipeline-box {
        background: #1a3a5c;
        color: white;
        border-radius: 6px;
        padding: 0.7rem 1rem;
        text-align: center;
        font-size: 0.82rem;
        font-weight: 500;
    }
    .pipeline-arrow {
        text-align: center;
        font-size: 1.2rem;
        color: #888;
        padding: 0.2rem 0;
    }
    .roadmap-item {
        background: #f0f4ff;
        border-left: 3px solid #6c8ebf;
        padding: 0.5rem 0.8rem;
        border-radius: 3px;
        margin-bottom: 0.4rem;
        font-size: 0.83rem;
        color: #333;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.title("TrafficPulse")
st.caption("Event-Driven Congestion Management System — Bengaluru Traffic Police")

st.markdown("---")

# --- Key metrics ---
data_path = Path("data/events.csv")
if data_path.exists():
    df = pd.read_csv(data_path, na_values=['NULL', 'null', ''])
    total = len(df)
    high = int((df['priority'].str.lower() == 'high').sum()) if 'priority' in df.columns else 0
    closures = int(df['requires_road_closure'].astype(str).str.upper().eq('TRUE').sum()) if 'requires_road_closure' in df.columns else 0
    causes = df['event_cause'].nunique() if 'event_cause' in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Incidents", f"{total:,}", "Nov 2023 – Apr 2024")
    c2.metric("High Priority", f"{high:,}", f"{high/total*100:.0f}% of total")
    c3.metric("Road Closures Required", f"{closures:,}", f"{closures/total*100:.1f}% of events")
    c4.metric("Incident Cause Types", str(causes))
else:
    st.warning("Data file not found at data/events.csv")

st.markdown("---")

# --- System pipeline ---
st.subheader("How It Works")

p1, arr1, p2, arr2, p3, arr3, p4 = st.columns([3, 0.5, 3, 0.5, 3, 0.5, 3])

with p1:
    st.markdown("""
    <div class="pipeline-box">
        Data Sources<br>
        <span style="font-weight:300;font-size:0.75rem;">
        Astram incidents<br>Citizen reports<br>Historical patterns
        </span>
    </div>
    """, unsafe_allow_html=True)
with arr1:
    st.markdown('<div class="pipeline-arrow" style="padding-top:1.2rem;">&#8594;</div>', unsafe_allow_html=True)
with p2:
    st.markdown("""
    <div class="pipeline-box">
        Prediction Engine<br>
        <span style="font-weight:300;font-size:0.75rem;">
        Severity classifier<br>Hotspot analysis<br>Impact scoring
        </span>
    </div>
    """, unsafe_allow_html=True)
with arr2:
    st.markdown('<div class="pipeline-arrow" style="padding-top:1.2rem;">&#8594;</div>', unsafe_allow_html=True)
with p3:
    st.markdown("""
    <div class="pipeline-box">
        Resource Dispatch<br>
        <span style="font-weight:300;font-size:0.75rem;">
        Manpower allocation<br>Tow truck routing<br>Diversion plans
        </span>
    </div>
    """, unsafe_allow_html=True)
with arr3:
    st.markdown('<div class="pipeline-arrow" style="padding-top:1.2rem;">&#8594;</div>', unsafe_allow_html=True)
with p4:
    st.markdown("""
    <div class="pipeline-box">
        Learning Loop<br>
        <span style="font-weight:300;font-size:0.75rem;">
        After-action review<br>Model retraining<br>Playbook updates
        </span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Modules ---
st.subheader("Modules")

left_col, right_col = st.columns(2)

modules_left = [
    ("Live Ops", "Real-time incident heatmap, corridor risk, tow truck pre-positioning"),
    ("Prediction Tool", "Input any event — get severity probability and resource recommendation"),
    ("Citizen Reports", "Public incident submission with auto-verification and police dispatch view"),
]
modules_right = [
    ("After-Action Report", "Predicted vs. actual outcomes; response time analytics and trend tracking"),
    ("Leaderboards", "Officer response scores and citizen reporter rankings"),
    ("Violation Hotspots", "Recurring incident locations flagged for escalation"),
]

with left_col:
    for name, desc in modules_left:
        st.markdown(f"""
        <div class="module-card">
            <h4>{name}</h4>
            <p>{desc}</p>
        </div>
        """, unsafe_allow_html=True)

with right_col:
    for name, desc in modules_right:
        st.markdown(f"""
        <div class="module-card">
            <h4>{name}</h4>
            <p>{desc}</p>
        </div>
        """, unsafe_allow_html=True)

# --- Problem statement alignment ---
st.subheader("Problem Statement Alignment")
st.caption('PS2 — "Event-Driven Congestion (Planned & Unplanned)" — mapped to what\'s implemented.')

ps_rows = [
    ("Forecast event impact in advance",
     "Severity model (priority/closure probability) + Planned Event Mode, which scales the forecast by expected attendance for festivals, rallies, and sports events."),
    ("Recommend optimal manpower",
     "Personnel counts auto-scaled by severity tier and, for planned events, attendance."),
    ("Recommend barricading",
     "Barricade counts per incident, shown in both the Prediction tool and live Citizen Reports."),
    ("Recommend diversion plans",
     "Real Mappls-routed map: direct path through the congested corridor vs. the same trip diverted via the alternate, both ending at the same destination."),
    ('"Resource deployment is experience-driven" (named gap)',
     "Cascade Risk predictor, Emergency Corridor ETA (real hospital routing), and Flood-Prone flagging replace guesswork with computed, data-backed signals."),
    ('"No post-event learning system" (named gap)',
     "After-Action Report tracks the model's accuracy month-over-month, separates in-sample from held-out performance, and flags when a retrain is warranted."),
    ("Historical and real-time data",
     "Astram historical dataset + a Live Replay mode that streams it in timestamp order to simulate a live feed, plus live citizen reports and live Mappls ETA/routing."),
    ("Planned & unplanned events",
     "event_type field throughout, with Planned Event Mode specifically for the planned side (rallies, festivals, sports, construction)."),
]

row_html = "".join(
    f'<tr style="border-bottom:1px solid #e0e0e0;">'
    f'<td style="padding:8px 10px;width:32%;vertical-align:top;color:#1a3a5c;font-weight:600;">{req}</td>'
    f'<td style="padding:8px 10px;vertical-align:top;color:#444;">{answer}</td>'
    f'</tr>'
    for req, answer in ps_rows
)
ps_table_html = (
    '<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">'
    + row_html + "</table>"
)
st.markdown(ps_table_html, unsafe_allow_html=True)

st.markdown("---")

# --- Roadmap / Prevention layer ---
st.subheader("Prevention Layer — Phase 2 Roadmap")
st.caption("Features designed for when external government data feeds become available.")

road_col1, road_col2 = st.columns(2)
with road_col1:
    for item in [
        "BBMP construction permit intercept — auto-create traffic event from dig permits",
        "Sports & festival schedule scraper — pre-forecast crowd-driven congestion",
        "Rally permit integration — route closure plan mandated before approval",
    ]:
        st.markdown(f'<div class="roadmap-item">{item}</div>', unsafe_allow_html=True)

with road_col2:
    for item in [
        "Shared incident bus — auto-route events to BBMP, BESCOM, BWSSB by cause",
        "Repair SLA tracker — work order auto-raised for repeat pothole locations",
        "Mappls live traffic SDK overlay — blocked on account tile-serving entitlement; REST routing/ETA already integrated",
    ]:
        st.markdown(f'<div class="roadmap-item">{item}</div>', unsafe_allow_html=True)

st.markdown("---")
st.caption("Built on Astram incident data provided by the hackathon.")
