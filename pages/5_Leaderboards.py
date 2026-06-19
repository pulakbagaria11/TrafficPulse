import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data
from src.officer_score import compute_officer_scores, officer_summary
from src.reporter_score import get_leaderboard

st.set_page_config(page_title="Leaderboards | TrafficPulse", layout="wide")
st.title("Leaderboards")
st.caption("Officer response performance and citizen reporter contributions.")

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

tab1, tab2 = st.tabs(["Officer Response Scores", "Reporter Points"])

# --- Officer scores ---
with tab1:
    st.subheader("Officer Response Performance")

    summary = officer_summary(df)
    if summary:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Officers Tracked", summary.get('total_officers', 0))
        c2.metric("Top Performer", str(summary.get('top_performer', 'N/A')))
        c3.metric("Avg Score", summary.get('avg_score', 'N/A'))
        if summary.get('avg_response_mins') is not None:
            c4.metric("Avg Response (min)", summary['avg_response_mins'])
        st.markdown("---")

    scores = compute_officer_scores(df)

    if scores.empty:
        st.info(
            "Officer scores require an assigned officer ID column "
            "(assigned_to_police_id) and closed event timestamps."
        )
    else:
        col1, col2 = st.columns([2, 1])

        with col1:
            display = scores.copy()
            rename = {
                'officer_id': 'Officer ID',
                'rank': 'Rank',
                'total_events': 'Events Handled',
                'avg_response_mins': 'Avg Response (min)',
                'high_priority_count': 'High Priority',
                'volume_score': 'Volume Score',
                'speed_score': 'Speed Score',
                'severity_score': 'Severity Score',
                'total_score': 'Total Score',
            }
            display = display.rename(columns={k: v for k, v in rename.items() if k in display.columns})
            show_cols = [v for v in rename.values() if v in display.columns]
            st.dataframe(display[show_cols].head(30), use_container_width=True, hide_index=True)

        with col2:
            st.markdown("**Score Breakdown**")
            st.markdown("""
            | Component | Weight |
            |---|---|
            | Events handled | 40% |
            | Response speed | 40% |
            | High-priority events | 20% |

            Scores are normalized within the dataset.
            Officers with fewer than 3 events are excluded.
            """)

        if len(scores) >= 5:
            top10 = scores.head(10).sort_values('total_score')
            fig = px.bar(
                top10,
                x='total_score',
                y=top10['officer_id'].astype(str),
                orientation='h',
                color_discrete_sequence=['#1a3a5c'],
                labels={'total_score': 'Score', 'y': 'Officer'},
            )
            fig.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=320,
                title='Top 10 Officers',
            )
            st.plotly_chart(fig, use_container_width=True)

# --- Reporter scores ---
with tab2:
    st.subheader("Citizen Reporter Points")
    st.caption(
        "Points are awarded when citizen reports are verified. "
        "Auto-verification triggers when 3 or more reports arrive from the same area. "
        "Below shows demo data alongside any reports submitted this session."
    )

    board = get_leaderboard()

    col1, col2 = st.columns([2, 1])

    with col1:
        display_board = board.copy().rename(columns={
            'reporter_id': 'Reporter ID',
            'rank': 'Rank',
            'reports_submitted': 'Reports Submitted',
            'verified_reports': 'Verified',
            'total_points': 'Points',
        })
        st.dataframe(display_board, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**How points work**")
        st.markdown("""
        | Action | Points |
        |---|---|
        | Report verified | 10 |
        | Pending report | 0 |

        Verification happens automatically when 3+
        reports arrive within ~200m of each other.

        Future: accuracy bonus for reports that
        match eventual Astram log entries.
        """)

    if len(board) > 0:
        top5 = board.head(5)
        fig2 = px.bar(
            top5,
            x='total_points',
            y=top5['reporter_id'].astype(str),
            orientation='h',
            color_discrete_sequence=['#1a3a5c'],
            labels={'total_points': 'Points', 'y': 'Reporter'},
        )
        fig2.update_layout(
            margin=dict(l=0, r=0, t=30, b=0),
            height=240,
            title='Top 5 Reporters',
        )
        st.plotly_chart(fig2, use_container_width=True)
