import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label
from src.severity_model import train_models
from src.after_action import get_closed_events, response_time_stats, summary_by_cause, accuracy_by_cause
from src.corridor import get_monthly_trend

st.set_page_config(page_title="After-Action | TrafficPulse", layout="wide")
st.markdown("<style>h1,h2,h3{font-weight:600;}.stMetric label{font-size:0.8rem;color:#666;}</style>",
            unsafe_allow_html=True)

st.title("After-Action Report")
st.caption("Track response quality over time and drive continuous improvement.")

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

# --- Month filter ---
with st.sidebar:
    st.header("Filter")
    if 'month' in df.columns:
        month_names = {11: 'Nov 2023', 12: 'Dec 2023', 1: 'Jan 2024',
                       2: 'Feb 2024', 3: 'Mar 2024', 4: 'Apr 2024'}
        available = sorted(df['month'].dropna().unique().tolist())
        selected = st.multiselect(
            "Month", options=available,
            format_func=lambda m: month_names.get(int(m), str(m)),
            default=[],
        )
        if selected:
            df = df[df['month'].isin(selected)]

filtered_df = df

# --- Response time ---
st.subheader("Response Time")
stats = response_time_stats(filtered_df)

if stats:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Closed Events", f"{stats['count']:,}")
    c2.metric("Avg Response", f"{stats['mean_mins']} min")
    c3.metric("Median Response", f"{stats['median_mins']} min")
    c4.metric("90th Percentile", f"{stats['p90_mins']} min")
else:
    st.info("No closed events with response time data available.")

st.markdown("---")

# --- Trend over time ---
st.subheader("Incident Trend")
trend = get_monthly_trend(filtered_df)
if not trend.empty:
    fig_trend = px.bar(
        trend, x='month_name', y='incidents',
        color_discrete_sequence=['#1a3a5c'],
        labels={'month_name': 'Month', 'incidents': 'Incidents'},
    )
    if 'high_priority' in trend.columns:
        fig_trend.add_scatter(
            x=trend['month_name'], y=trend['high_priority'],
            name='High Priority', mode='lines+markers',
            line=dict(color='#c0392b', width=2),
        )
    fig_trend.update_layout(
        margin=dict(l=0, r=0, t=10, b=0), height=280,
        legend=dict(orientation='h', y=1.05),
    )
    st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# --- Outcome by cause ---
st.subheader("Outcome by Cause")
summary = summary_by_cause(filtered_df)
if not summary.empty:
    s = summary.copy()
    s['event_cause'] = s['event_cause'].apply(cause_label)

    chart_col, metric_col = st.columns([2, 1])

    with chart_col:
        if 'high_priority_rate' in s.columns:
            fig_cause = px.bar(
                s.head(10),
                x='high_priority_rate',
                y='event_cause',
                orientation='h',
                color_discrete_sequence=['#c0392b'],
                labels={'high_priority_rate': 'High Priority Rate', 'event_cause': ''},
                text='high_priority_rate',
            )
            fig_cause.update_traces(texttemplate='%{text:.0%}', textposition='outside')
            fig_cause.update_layout(
                margin=dict(l=0, r=0, t=10, b=0), height=300,
                xaxis_tickformat='.0%',
            )
            st.plotly_chart(fig_cause, use_container_width=True)

    with metric_col:
        if 'duration_mins' in s.columns:
            fastest = s.dropna(subset=['duration_mins']).sort_values('duration_mins').iloc[0]
            slowest = s.dropna(subset=['duration_mins']).sort_values('duration_mins').iloc[-1]
            st.metric("Fastest avg response", f"{fastest['duration_mins']} min",
                      fastest['event_cause'])
            st.metric("Slowest avg response", f"{slowest['duration_mins']} min",
                      slowest['event_cause'])

st.markdown("---")

# --- Prediction accuracy ---
st.subheader("Prediction Accuracy on Historical Events")
closed = get_closed_events(filtered_df)

if len(closed) > 10:
    with st.spinner("Computing accuracy..."):
        models, encoders, feature_cols = train_models(df)
        acc_df = accuracy_by_cause(closed, models, encoders, feature_cols)

    if not acc_df.empty:
        overall = acc_df['correct'].mean()

        ac1, ac2 = st.columns(2)
        ac1.metric("Overall Accuracy", f"{overall:.1%}")
        ac2.metric("Events evaluated", len(acc_df))

        by_cause = (
            acc_df.groupby('event_cause')
            .agg(accuracy=('correct', 'mean'), count=('correct', 'count'))
            .reset_index()
            .sort_values('count', ascending=False)
        )
        by_cause['label'] = by_cause['event_cause'].apply(cause_label)
        by_cause['accuracy_pct'] = (by_cause['accuracy'] * 100).round(1)

        fig_acc = px.bar(
            by_cause, x='accuracy_pct', y='label', orientation='h',
            color_discrete_sequence=['#1a3a5c'], text='accuracy_pct',
        )
        fig_acc.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_acc.update_layout(
            xaxis_title="Accuracy (%)", yaxis_title=None,
            xaxis_range=[0, 115],
            margin=dict(l=0, r=0, t=10, b=0), height=280,
        )
        st.plotly_chart(fig_acc, use_container_width=True)
    else:
        st.info("Not enough data for accuracy computation.")
else:
    st.info("Prediction accuracy requires closed events. Filter changes may reduce the available sample.")

st.markdown("---")

# --- Response time distribution ---
st.subheader("Response Time Distribution")
closed_all = get_closed_events(filtered_df)
if not closed_all.empty and 'duration_mins' in closed_all.columns:
    dur = closed_all['duration_mins'].dropna()
    fig_dist = px.histogram(dur, nbins=40, color_discrete_sequence=['#1a3a5c'],
                            labels={'value': 'Duration (min)', 'count': 'Events'})
    fig_dist.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                           height=230, xaxis_title='Duration (min)', yaxis_title='Events')
    st.plotly_chart(fig_dist, use_container_width=True)

st.caption("For full event-level tables and the response playbook, see the Stats & Data Analysis page.")
