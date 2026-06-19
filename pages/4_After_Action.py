import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label
from src.severity_model import train_models
from src.after_action import (
    get_closed_events, response_time_stats,
    summary_by_cause, accuracy_by_cause
)
from src.playbook import build_playbook, top_causes_by_time

st.set_page_config(page_title="After-Action | TrafficPulse", layout="wide")
st.title("After-Action Report")
st.caption("Predicted vs. actual outcomes on historically closed events. Drives continuous model improvement.")

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

closed = get_closed_events(df)
has_closed = not closed.empty

# --- Response time summary ---
st.subheader("Response Time Summary")
stats = response_time_stats(df)

if stats:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Closed Events", f"{stats['count']:,}")
    c2.metric("Avg Response (min)", stats['mean_mins'])
    c3.metric("Median Response (min)", stats['median_mins'])
    c4.metric("90th Percentile (min)", stats['p90_mins'])
else:
    st.info("No closed events with response time data available.")

st.markdown("---")

# --- Summary by cause ---
st.subheader("Outcome by Event Cause")
summary = summary_by_cause(df)

if not summary.empty:
    display = summary.copy()
    display['event_cause'] = display['event_cause'].apply(cause_label)
    rename = {
        'event_cause': 'Cause',
        'event_count': 'Events',
        'duration_mins': 'Median Duration (min)',
        'high_priority_rate': 'High Priority Rate',
        'closure_rate': 'Closure Rate',
    }
    display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.info("No closed events found for outcome analysis.")

# --- Duration distribution ---
if has_closed and 'duration_mins' in closed.columns:
    st.markdown("---")
    st.subheader("Response Time Distribution")

    dur_data = closed['duration_mins'].dropna()
    fig = px.histogram(
        dur_data, nbins=40,
        labels={'value': 'Duration (min)', 'count': 'Events'},
        color_discrete_sequence=['#1a3a5c'],
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0),
        height=280,
        xaxis_title="Duration (min)",
        yaxis_title="Events",
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Prediction accuracy ---
st.markdown("---")
st.subheader("Prediction Accuracy on Closed Events")

if has_closed and len(closed) > 10:
    with st.spinner("Running predictions on historical closed events..."):
        models, encoders, feature_cols = train_models(df)
        acc_df = accuracy_by_cause(closed, models, encoders, feature_cols)

    if not acc_df.empty:
        overall_acc = acc_df['correct'].mean()
        st.metric("Overall Accuracy", f"{overall_acc:.1%}")

        by_cause = (
            acc_df.groupby('event_cause')
            .agg(accuracy=('correct', 'mean'), count=('correct', 'count'))
            .reset_index()
            .sort_values('count', ascending=False)
        )
        by_cause['cause_label'] = by_cause['event_cause'].apply(cause_label)
        by_cause['accuracy_pct'] = (by_cause['accuracy'] * 100).round(1)

        fig2 = px.bar(
            by_cause,
            x='accuracy_pct',
            y='cause_label',
            orientation='h',
            color_discrete_sequence=['#1a3a5c'],
            text='accuracy_pct',
        )
        fig2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig2.update_layout(
            xaxis_title="Accuracy (%)", yaxis_title=None,
            xaxis_range=[0, 110],
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Not enough closed events with complete data to compute accuracy.")
else:
    st.info("Prediction accuracy requires closed events with a start and close time.")

# --- Playbook ---
st.markdown("---")
st.subheader("Response Playbook")
st.caption("Derived from historical patterns — median outcomes by cause and priority.")

playbook = build_playbook(df)
if not playbook.empty:
    display_pb = playbook.copy()
    display_pb['event_cause'] = display_pb['event_cause'].apply(cause_label)
    rename_pb = {
        'event_cause': 'Cause',
        'priority': 'Priority',
        'event_count': 'Events',
        'median_duration_mins': 'Median Duration (min)',
        'closure_rate': 'Closure Rate (%)',
        'peak_hour_rate': 'Peak Hour Rate (%)',
    }
    display_pb = display_pb.rename(columns={k: v for k, v in rename_pb.items() if k in display_pb.columns})
    st.dataframe(display_pb, use_container_width=True, hide_index=True)

# --- Time-of-day breakdown ---
st.markdown("---")
st.subheader("Peak Hour Breakdown")
col1, col2 = st.columns(2)
with col1:
    st.caption("Morning peak (07:00 - 10:00)")
    morning = top_causes_by_time(df, 7, 10)
    if not morning.empty:
        morning['cause'] = morning['cause'].apply(cause_label)
        st.dataframe(morning, use_container_width=True, hide_index=True)

with col2:
    st.caption("Evening peak (17:00 - 20:00)")
    evening = top_causes_by_time(df, 17, 20)
    if not evening.empty:
        evening['cause'] = evening['cause'].apply(cause_label)
        st.dataframe(evening, use_container_width=True, hide_index=True)
