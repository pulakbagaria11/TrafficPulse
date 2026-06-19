import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label, BENGALURU_CENTER
from src.severity_model import train_models, predict_event
from src.recommender import get_recommendation, calibrate_tiers
from src.diversion import get_route

st.set_page_config(page_title="Prediction | TrafficPulse", layout="wide")
st.title("Prediction and Resource Tool")
st.caption("Forecast impact severity and generate resource recommendations for any event.")

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

with st.spinner("Training model on historical data..."):
    models, encoders, feature_cols = train_models(df)

# --- Input form ---
st.subheader("Event Details")
form_col1, form_col2, form_col3 = st.columns(3)

all_causes = sorted(df['event_cause'].dropna().unique().tolist())
all_types = sorted(df['event_type'].dropna().unique().tolist()) if 'event_type' in df.columns else ['unplanned', 'planned']

with form_col1:
    event_cause = st.selectbox(
        "Event cause",
        options=all_causes,
        format_func=cause_label,
    )
    event_type = st.selectbox(
        "Event type",
        options=all_types,
        format_func=lambda x: x.replace('_', ' ').title(),
    )

with form_col2:
    lat = st.number_input("Latitude", value=12.9716, format="%.4f", min_value=12.7, max_value=13.2)
    lon = st.number_input("Longitude", value=77.5946, format="%.4f", min_value=77.3, max_value=77.8)

with form_col3:
    event_date = st.date_input("Date", value=datetime.today())
    event_time = st.time_input("Time (IST)", value=datetime.now().time())

hour = event_time.hour
weekday = event_date.weekday()
month = event_date.month

run = st.button("Run Prediction", type="primary")

st.markdown("---")

if run:
    preds = predict_event(
        models, encoders, feature_cols,
        event_cause=event_cause,
        event_type=event_type,
        lat=lat, lon=lon,
        hour=hour, weekday=weekday, month=month,
    )

    priority_prob = preds.get('priority', 0.5)
    closure_prob = preds.get('closure', 0.1)
    rec = get_recommendation(priority_prob, closure_prob, event_cause)

    # --- Results ---
    res_col1, res_col2, res_col3 = st.columns(3)

    tier_color = {
        'Critical': '#c0392b',
        'High': '#e67e22',
        'Medium': '#f39c12',
        'Low': '#27ae60',
    }.get(rec['tier'], '#1a3a5c')

    with res_col1:
        st.markdown(f"""
        <div style="background:{tier_color};color:white;padding:1rem 1.2rem;
                    border-radius:6px;text-align:center;">
            <div style="font-size:1rem;opacity:0.85;">Severity Tier</div>
            <div style="font-size:2rem;font-weight:700;">{rec['tier']}</div>
        </div>
        """, unsafe_allow_html=True)
        st.metric("Priority Probability", f"{priority_prob:.0%}")
        st.metric("Road Closure Probability", f"{closure_prob:.0%}")

    with res_col2:
        st.markdown("**Resource Recommendation**")
        st.metric("Personnel", rec['personnel'])
        st.metric("Barricades", rec['barricades'])
        st.metric("Target Response", f"{rec['response_minutes']} min")
        if rec.get('supervisor'):
            st.warning("Supervisor deployment required")
        if rec.get('diversion'):
            st.info("Diversion plan required")

    with res_col3:
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
                'threshold': {
                    'line': {'color': '#1a3a5c', 'width': 2},
                    'thickness': 0.75,
                    'value': 50,
                },
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # --- Diversion ---
    if rec.get('diversion'):
        st.markdown("---")
        st.subheader("Diversion Route")
        with st.spinner("Fetching alternate routes from Mappls..."):
            routes, err = get_route(lat - 0.01, lon - 0.01, lat + 0.01, lon + 0.01)

        if routes:
            for i, r in enumerate(routes):
                st.markdown(
                    f"**Route {i + 1}**: {r.get('summary', 'Alternate')} — "
                    f"{r.get('distance_km', '?')} km, "
                    f"~{r.get('duration_min', '?')} min"
                )
        else:
            st.info(f"Route suggestion unavailable: {err}")

    # --- Feature importance ---
    st.markdown("---")
    st.subheader("What drives this prediction")
    if 'priority' in models:
        fi = models['priority']['feature_importance']
        fi_df = (
            pd.DataFrame(list(fi.items()), columns=['feature', 'importance'])
            .sort_values('importance', ascending=True)
            .tail(10)
        )
        fi_df['feature'] = fi_df['feature'].str.replace('_enc', '').str.replace('_', ' ').str.title()
        import plotly.express as px
        fig3 = px.bar(
            fi_df, x='importance', y='feature',
            orientation='h', color_discrete_sequence=['#1a3a5c'],
        )
        fig3.update_layout(
            xaxis_title="Importance", yaxis_title=None,
            margin=dict(l=0, r=0, t=10, b=0), height=280,
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.caption(f"Model accuracy on test set: {models['priority']['accuracy']:.1%}")

else:
    st.info("Fill in the event details above and click Run Prediction.")

# --- Calibration table ---
with st.expander("Historical rates by event cause"):
    calib = calibrate_tiers(df)
    if calib:
        calib_df = pd.DataFrame(calib).T.reset_index().rename(columns={'index': 'cause'})
        calib_df['cause'] = calib_df['cause'].apply(cause_label)
        st.dataframe(calib_df, use_container_width=True, hide_index=True)
