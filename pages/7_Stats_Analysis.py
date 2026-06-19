import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, cause_label
from src.corridor import get_corridor_stats, get_monthly_trend, get_weekday_trend
from src.playbook import build_playbook
from src.officer_score import compute_officer_scores
from src.recommender import calibrate_tiers

st.set_page_config(page_title="Stats | TrafficPulse", layout="wide")
st.markdown("<style>h1,h2,h3{font-weight:600;}.stMetric label{font-size:0.8rem;color:#666;}</style>",
            unsafe_allow_html=True)

st.title("Stats and Data Analysis")
st.caption("Detailed breakdowns for analysis and presentation. All tables are downloadable.")

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Incident Overview", "Corridor Analysis", "Playbook", "Officer Data", "Raw Events"
])

# ── Tab 1: Incident Overview ──────────────────────────────────────────────────
with tab1:
    st.subheader("Dataset Summary")
    total = len(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events", f"{total:,}")
    if 'priority_enc' in df.columns:
        c2.metric("High Priority", f"{int(df['priority_enc'].sum()):,}")
    if 'closure_enc' in df.columns:
        c3.metric("Road Closures", f"{int(df['closure_enc'].sum()):,}")
    if 'event_type' in df.columns:
        planned = int((df['event_type'] == 'planned').sum())
        c4.metric("Planned Events", f"{planned:,}")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Cause Distribution")
        cause_df = (
            df['event_cause'].value_counts()
            .reset_index()
            .rename(columns={'event_cause': 'cause', 'count': 'incidents'})
        )
        cause_df['label'] = cause_df['cause'].apply(cause_label)
        cause_df['pct'] = (cause_df['incidents'] / total * 100).round(1)

        fig1 = px.bar(cause_df, x='incidents', y='label', orientation='h',
                      color_discrete_sequence=['#1a3a5c'],
                      labels={'incidents': 'Incidents', 'label': ''})
        fig1.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360)
        st.plotly_chart(fig1, use_container_width=True)

        st.download_button("Download cause data (.csv)",
                           data=cause_df.to_csv(index=False),
                           file_name="cause_distribution.csv", mime="text/csv")

    with col2:
        st.subheader("Priority by Cause")
        calib = calibrate_tiers(df)
        if calib:
            calib_df = (
                pd.DataFrame(calib).T
                .reset_index()
                .rename(columns={'index': 'cause'})
                .sort_values('high_priority_rate', ascending=False)
            )
            calib_df['label'] = calib_df['cause'].apply(cause_label)

            fig2 = px.bar(calib_df, x='high_priority_rate', y='label',
                          orientation='h', color_discrete_sequence=['#c0392b'],
                          labels={'high_priority_rate': 'High Priority Rate', 'label': ''},
                          text='high_priority_rate')
            fig2.update_traces(texttemplate='%{text:.0%}', textposition='outside')
            fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360,
                               xaxis_tickformat='.0%')
            st.plotly_chart(fig2, use_container_width=True)

            st.download_button("Download calibration data (.csv)",
                               data=calib_df.to_csv(index=False),
                               file_name="cause_calibration.csv", mime="text/csv")

    st.markdown("---")

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Monthly Trend")
        trend = get_monthly_trend(df)
        if not trend.empty:
            fig3 = px.line(trend, x='month_name', y='incidents', markers=True,
                           color_discrete_sequence=['#1a3a5c'],
                           labels={'month_name': 'Month', 'incidents': 'Incidents'})
            if 'high_priority' in trend.columns:
                fig3.add_scatter(x=trend['month_name'], y=trend['high_priority'],
                                 name='High Priority', mode='lines+markers',
                                 line=dict(color='#c0392b', width=2))
            fig3.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=260,
                               legend=dict(orientation='h', y=1.1))
            st.plotly_chart(fig3, use_container_width=True)
            st.download_button("Download monthly trend (.csv)",
                               data=trend.to_csv(index=False),
                               file_name="monthly_trend.csv", mime="text/csv")

    with col4:
        st.subheader("Day of Week Pattern")
        wt = get_weekday_trend(df)
        if not wt.empty:
            fig4 = px.bar(wt, x='day', y='incidents', color_discrete_sequence=['#1a3a5c'],
                          labels={'day': '', 'incidents': 'Incidents'})
            fig4.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=260)
            st.plotly_chart(fig4, use_container_width=True)

    st.markdown("---")
    st.subheader("Hour of Day Pattern")
    if 'hour' in df.columns:
        hc = df['hour'].value_counts().sort_index().reset_index()
        hc.columns = ['hour', 'count']
        fig5 = px.bar(hc, x='hour', y='count', color_discrete_sequence=['#1a3a5c'],
                      labels={'hour': 'Hour (IST)', 'count': 'Incidents'})
        fig5.add_vline(x=7.5, line_dash='dot', line_color='red', annotation_text='Morning peak')
        fig5.add_vline(x=17.5, line_dash='dot', line_color='red', annotation_text='Evening peak')
        fig5.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=260)
        st.plotly_chart(fig5, use_container_width=True)


# ── Tab 2: Corridor Analysis ─────────────────────────────────────────────────
with tab2:
    st.subheader("Corridor Risk Analysis")
    top_n = st.slider("Show top N corridors", 5, 30, 15)
    corridor_stats = get_corridor_stats(df, top_n=top_n)

    if corridor_stats.empty:
        st.info("No corridor data in the dataset.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            fig_c1 = px.bar(corridor_stats, x='incidents', y='corridor', orientation='h',
                            color_discrete_sequence=['#1a3a5c'],
                            labels={'incidents': 'Incidents', 'corridor': ''})
            fig_c1.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=400)
            st.subheader("Incidents per Corridor")
            st.plotly_chart(fig_c1, use_container_width=True)

        with col2:
            if 'high_priority_rate_pct' in corridor_stats.columns:
                fig_c2 = px.bar(
                    corridor_stats.sort_values('high_priority_rate_pct', ascending=True),
                    x='high_priority_rate_pct', y='corridor', orientation='h',
                    color_discrete_sequence=['#c0392b'],
                    labels={'high_priority_rate_pct': 'High Priority %', 'corridor': ''},
                    text='high_priority_rate_pct',
                )
                fig_c2.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_c2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=400,
                                     xaxis_range=[0, 115])
                st.subheader("High Priority Rate by Corridor")
                st.plotly_chart(fig_c2, use_container_width=True)

        st.dataframe(corridor_stats, use_container_width=True, hide_index=True)
        st.download_button("Download corridor data (.csv)",
                           data=corridor_stats.to_csv(index=False),
                           file_name="corridor_analysis.csv", mime="text/csv")


# ── Tab 3: Playbook ───────────────────────────────────────────────────────────
with tab3:
    st.subheader("Response Playbook")
    st.caption("Median outcomes by cause and priority — derived from historical closed events.")
    playbook = build_playbook(df)
    if not playbook.empty:
        display_pb = playbook.copy()
        display_pb['event_cause'] = display_pb['event_cause'].apply(cause_label)
        rename_pb = {
            'event_cause': 'Cause', 'priority': 'Priority',
            'event_count': 'Events',
            'median_duration_mins': 'Median Duration (min)',
            'closure_rate': 'Closure Rate (%)',
            'peak_hour_rate': 'Peak Hour Rate (%)',
        }
        display_pb = display_pb.rename(columns={k: v for k, v in rename_pb.items()
                                                if k in display_pb.columns})
        show = [v for v in rename_pb.values() if v in display_pb.columns]
        st.dataframe(display_pb[show], use_container_width=True, hide_index=True)
        st.download_button("Download playbook (.csv)",
                           data=playbook.to_csv(index=False),
                           file_name="response_playbook.csv", mime="text/csv")


# ── Tab 4: Officer Data ───────────────────────────────────────────────────────
with tab4:
    st.subheader("Officer Event Data")
    st.caption("Full officer scoring data. Reflects events with assigned officer IDs in the dataset.")
    scores = compute_officer_scores(df)
    if scores.empty:
        st.info("No officer assignment data found.")
    else:
        rename_o = {
            'rank': 'Rank', 'officer_id': 'Officer ID',
            'total_events': 'Events', 'avg_response_mins': 'Avg Response (min)',
            'high_priority_count': 'High Priority', 'volume_score': 'Volume Score',
            'speed_score': 'Speed Score', 'severity_score': 'Severity Score',
            'total_score': 'Total Score',
        }
        disp = scores.rename(columns={k: v for k, v in rename_o.items() if k in scores.columns})
        show_o = [v for v in rename_o.values() if v in disp.columns]
        st.dataframe(disp[show_o], use_container_width=True, hide_index=True)
        st.download_button("Download officer data (.csv)",
                           data=scores.to_csv(index=False),
                           file_name="officer_scores.csv", mime="text/csv")


# ── Tab 5: Raw Events ─────────────────────────────────────────────────────────
with tab5:
    st.subheader("Raw Event Data")

    col1, col2, col3 = st.columns(3)
    with col1:
        cause_filter = st.multiselect("Filter by cause",
                                      options=sorted(df['event_cause'].dropna().unique()),
                                      format_func=cause_label, default=[])
    with col2:
        priority_filter = st.selectbox("Filter by priority",
                                       options=["All", "High", "Low"])
    with col3:
        search = st.text_input("Search description / corridor", placeholder="e.g. MG Road")

    filtered = df.copy()
    if cause_filter:
        filtered = filtered[filtered['event_cause'].isin(cause_filter)]
    if priority_filter != "All" and 'priority' in filtered.columns:
        filtered = filtered[filtered['priority'].str.lower() == priority_filter.lower()]
    if search:
        mask = pd.Series(False, index=filtered.index)
        for col in ['description', 'corridor', 'junction', 'comment', 'address']:
            if col in filtered.columns:
                mask |= filtered[col].fillna('').str.contains(search, case=False)
        filtered = filtered[mask]

    display_cols = [c for c in [
        'start_datetime', 'event_cause', 'event_type', 'priority',
        'requires_road_closure', 'corridor', 'zone', 'junction',
        'police_station', 'duration_mins',
    ] if c in filtered.columns]

    st.caption(f"Showing {len(filtered):,} of {len(df):,} events")
    st.dataframe(
        filtered[display_cols].sort_values('start_datetime', ascending=False)
        if 'start_datetime' in filtered.columns else filtered[display_cols],
        use_container_width=True, hide_index=True, height=400,
    )
    st.download_button(
        "Download filtered data (.csv)",
        data=filtered[display_cols].to_csv(index=False),
        file_name="filtered_events.csv", mime="text/csv",
    )
