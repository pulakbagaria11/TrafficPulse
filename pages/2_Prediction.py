import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_folium import st_folium

from src.data_prep import load_data, cause_label, BENGALURU_CENTER
from src.severity_model import train_models, predict_event
from src.recommender import get_recommendation, scale_for_crowd_size
from src.diversion import get_corridor_alternates, make_route_map
from src.emergency import get_emergency_advisory
from src.cascade import top_cascade_for_corridor
from src.corridor import get_corridor_stats

st.set_page_config(page_title="Prediction | TrafficPulse", layout="wide")
st.markdown("<style>h1,h2,h3{font-weight:600;}.stMetric label{font-size:0.8rem;color:#666;}</style>",
            unsafe_allow_html=True)

st.title("Prediction and Resource Tool")
st.caption("Enter event details to get a severity forecast and recommended response.")

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

with st.spinner("Loading model..."):
    models, encoders, feature_cols = train_models(df)

BENGALURU_AREAS = {
    'Majestic / City Centre': (12.9767, 77.5713),
    'Koramangala': (12.9352, 77.6245),
    'Indiranagar': (12.9784, 77.6408),
    'Whitefield': (12.9698, 77.7500),
    'Electronic City': (12.8458, 77.6601),
    'Hebbal': (13.0358, 77.5970),
    'Rajajinagar': (12.9915, 77.5521),
    'Marathahalli': (12.9591, 77.6972),
    'Yeshwanthpur': (13.0258, 77.5461),
    'Tumkur Road corridor': (13.0200, 77.5100),
    'Bannerghatta Road corridor': (12.8875, 77.5946),
    'Outer Ring Road': (12.9698, 77.7100),
    'Silk Board junction': (12.9177, 77.6237),
    'K R Puram': (13.0078, 77.6942),
}

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# --- Input form ---
st.subheader("Event Details")
col1, col2, col3 = st.columns(3)

all_causes = sorted(df['event_cause'].dropna().unique().tolist())
all_types = ['unplanned', 'planned'] if 'event_type' not in df.columns else sorted(df['event_type'].dropna().unique())

with col1:
    event_cause = st.selectbox("Event cause", options=all_causes, format_func=cause_label)
    event_type = st.selectbox("Event type", options=all_types,
                               format_func=lambda x: x.replace('_', ' ').title())

with col2:
    area = st.selectbox("Location / area", options=list(BENGALURU_AREAS.keys()))
    lat, lon = BENGALURU_AREAS[area]
    st.caption(f"Coordinates: {lat:.4f}, {lon:.4f}")

with col3:
    event_date = st.date_input("Date", value=datetime.today())
    event_time = st.time_input("Time (IST)", value=datetime.now().replace(second=0, microsecond=0).time())

hour = event_time.hour
weekday = event_date.weekday()
month = event_date.month

st.markdown(
    f"<span style='font-size:0.82rem;color:#666;'>"
    f"Context: {DAY_NAMES[weekday]}, {event_time.strftime('%H:%M')} IST, "
    f"{'peak hour' if (7 <= hour <= 10 or 17 <= hour <= 20) else 'off-peak'}, "
    f"{'weekend' if weekday >= 5 else 'weekday'}"
    f"</span>",
    unsafe_allow_html=True,
)

planned_event = st.checkbox(
    "Planned event (festival / rally / sports) — scale resources by expected attendance"
)
attendance = 0
if planned_event:
    attendance = st.number_input(
        "Expected attendance", min_value=0, value=5000, step=500,
    )

run = st.button("Run Prediction", type="primary")
st.markdown("---")

if run:
    preds = predict_event(
        models, encoders, feature_cols,
        event_cause=event_cause, event_type=event_type,
        lat=lat, lon=lon, hour=hour, weekday=weekday, month=month,
    )
    priority_prob = preds.get('priority', 0.5)
    closure_prob = preds.get('closure', 0.1)
    rec = get_recommendation(priority_prob, closure_prob, event_cause)
    if planned_event and attendance > 0:
        rec = scale_for_crowd_size(rec, attendance)

    tier_color = {'Critical': '#c0392b', 'High': '#e67e22',
                  'Medium': '#f39c12', 'Low': '#27ae60'}.get(rec['tier'], '#1a3a5c')

    corridor_val = df[df['event_cause'] == event_cause]['corridor'].dropna()
    top_corridor = corridor_val.value_counts().index[0] if len(corridor_val) > 0 else None
    alts = get_corridor_alternates(top_corridor or '')
    top_alt = (alts or ['ORR North 1'])[0]

    # --- Result layout ---
    r1, r2, r3 = st.columns(3)

    with r1:
        st.markdown(
            f"""<div style="background:{tier_color};color:white;padding:1.2rem;
            border-radius:6px;text-align:center;margin-bottom:1rem;">
            <div style="font-size:0.85rem;opacity:0.85;margin-bottom:4px;">Severity Tier</div>
            <div style="font-size:2.2rem;font-weight:700;">{rec['tier']}</div>
            <div style="font-size:0.8rem;opacity:0.75;margin-top:4px;">
            {area}</div>
            </div>""",
            unsafe_allow_html=True,
        )
        st.metric("High Priority Probability", f"{priority_prob:.0%}")
        st.metric("Road Closure Probability", f"{closure_prob:.0%}")
        if rec.get('supervisor'):
            st.warning("Supervisor required")
        if rec.get('diversion'):
            st.info("Diversion plan required")
        if rec.get('crowd_attendance'):
            st.caption(f"Resources scaled up for an expected attendance of {rec['crowd_attendance']:,}.")

    with r2:
        st.markdown("**Recommended Response**")
        st.markdown("---")
        rc1, rc2 = st.columns(2)
        rc1.metric("Personnel", rec['personnel'])
        rc2.metric("Barricades", rec['barricades'])
        st.metric("Target Response Time", f"{rec['response_minutes']} min")

        st.markdown("<br>**Event context used:**", unsafe_allow_html=True)
        context_items = [
            f"Cause: {cause_label(event_cause)}",
            f"Type: {event_type.title()}",
            f"Time: {event_time.strftime('%H:%M')} IST ({DAY_NAMES[weekday]})",
            f"Area: {area}",
        ]
        for item in context_items:
            st.markdown(f"- {item}")

    with r3:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(priority_prob * 100, 1),
            number={'suffix': '%'},
            title={'text': 'High Priority Probability'},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': tier_color},
                'steps': [
                    {'range': [0, 40], 'color': '#d5f5e3'},
                    {'range': [40, 70], 'color': '#fdebd0'},
                    {'range': [70, 100], 'color': '#fadbd8'},
                ],
                'threshold': {'line': {'color': '#1a3a5c', 'width': 2},
                              'thickness': 0.75, 'value': 50},
            }
        ))
        fig.update_layout(height=240, margin=dict(l=20, r=20, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- Emergency corridor advisory ---
    advisory = get_emergency_advisory(df, lat, lon, event_cause, rec)
    if advisory:
        st.markdown("---")
        barricade_note = f" {rec['barricades']} barricade(s) recommended at the hold point." if rec.get('barricades') else ""
        redirect_note = f" Redirect general traffic via {top_alt}." if top_corridor else ""
        st.warning(
            f"**Emergency Corridor** — Hold cross-traffic at "
            f"**{advisory['junction']}** for approximately "
            f"**{advisory['eta_mins']} min** to allow emergency vehicles through from "
            f"{advisory['hub']}.{redirect_note}{barricade_note}"
        )

    # --- Diversion ---
    if rec.get('diversion'):
        st.markdown("---")
        st.subheader("Diversion Plan")

        dc1, dc2, dc3 = st.columns(3)
        dc1.markdown("**Affected corridor**")
        dc1.markdown(top_corridor or "Unknown — check location")

        dc2.markdown("**Alternate corridors**")
        for a in (alts or ['ORR North 1', 'Hosur Road']):
            dc2.markdown(f"- {a}")

        dc3.markdown("**Recommended action**")
        dc3.markdown(
            "Post diversion signs at junction entry points. "
            "Alert field officers on alternate corridors. "
            "See route map below for current conditions."
        )

        if top_corridor:
            corridor_stats = get_corridor_stats(df, top_n=999)
            stat_row = corridor_stats[corridor_stats['corridor'] == top_corridor]
            avg_duration = (
                stat_row.iloc[0]['avg_duration_mins']
                if not stat_row.empty and 'avg_duration_mins' in stat_row.columns
                else rec['response_minutes'] * 3
            )
            expected_congestion_mins = round(closure_prob * avg_duration)

            ic1, ic2 = st.columns(2)
            ic1.metric("Estimated Congestion Avoided", f"~{expected_congestion_mins} min")
            ic2.caption(
                f"Closure probability ({closure_prob:.0%}) x historical average closure "
                f"duration on {top_corridor} ({avg_duration:.0f} min) -- the expected disruption "
                f"this diversion plan keeps off the road, not a guarantee."
            )

            st.caption(f"Source: historical Astram data — {int((corridor_val == top_corridor).sum())} incidents recorded on {top_corridor}.")

            cascade_note = top_cascade_for_corridor(df, top_corridor)
            if cascade_note:
                st.caption(
                    f"Cascade risk: incidents on {top_corridor} are historically followed by "
                    f"incidents on {cascade_note['alt_corridor']} within {cascade_note['window_hours']}h "
                    f"{cascade_note['uplift_x']}x more often than baseline — consider pre-positioning there too."
                )

            st.markdown("**Suggested Diversion Route**")
            route_map = make_route_map(df, lat, lon, top_corridor, top_alt)
            st_folium(route_map, width=None, height=420, returned_objects=[])

    # --- Feature importance ---
    st.markdown("---")
    st.subheader("What drove this prediction")
    if 'priority' in models:
        import plotly.express as px
        fi = models['priority']['feature_importance']
        fi_df = (
            pd.DataFrame(list(fi.items()), columns=['feature', 'importance'])
            .sort_values('importance', ascending=True).tail(8)
        )
        fi_df['feature'] = (fi_df['feature'].str.replace('_enc', '')
                            .str.replace('_', ' ').str.title())
        fig3 = px.bar(fi_df, x='importance', y='feature', orientation='h',
                      color_discrete_sequence=['#1a3a5c'])
        fig3.update_layout(xaxis_title="Importance", yaxis_title=None,
                           margin=dict(l=0, r=0, t=10, b=0), height=260)
        st.plotly_chart(fig3, use_container_width=True)
        p_acc = models['priority']['accuracy']
        p_te = models['priority'].get('test_size', '?')
        c_acc = models['closure']['accuracy'] if 'closure' in models else None
        st.caption(
            f"Trained on Nov–Feb, tested on Mar–Apr ({p_te} events). "
            f"Priority accuracy: {p_acc:.1%}"
            + (f"  |  Closure accuracy: {c_acc:.1%}" if c_acc else "")
        )

else:
    st.info("Fill in the event details above and click Run Prediction.")
    st.markdown("**Typical results:**")
    examples = [
        ("vehicle_breakdown", "Unplanned", "08:00", "High", "5 officers, 4 barricades"),
        ("vip_movement", "Planned", "10:00", "Critical", "12 officers, 10 barricades, diversion"),
        ("pot_holes", "Unplanned", "14:00", "Low", "1 officer"),
        ("public_event", "Planned", "19:00", "High", "7 officers, 6 barricades, diversion"),
    ]
    ex_df = pd.DataFrame(examples, columns=["Cause", "Type", "Time", "Typical Tier", "Typical Response"])
    st.dataframe(ex_df, use_container_width=True, hide_index=True)
