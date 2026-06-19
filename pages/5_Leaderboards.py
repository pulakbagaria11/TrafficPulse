import streamlit as st
import pandas as pd
import plotly.express as px
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data
from src.officer_score import compute_officer_scores, officer_summary
from src.reporter_score import get_leaderboard, get_all_reports, init_reports

st.set_page_config(page_title="Leaderboards | TrafficPulse", layout="wide")
st.markdown("<style>h1,h2,h3{font-weight:600;}.stMetric label{font-size:0.8rem;color:#666;}</style>",
            unsafe_allow_html=True)

st.title("Leaderboards")
init_reports()

df = load_data()
if df is None:
    st.error("Data not found. Place events.csv in the data/ folder.")
    st.stop()

tab1, tab2 = st.tabs(["Officer Response Scores", "Reporter Points"])

# --- Officer scores ---
with tab1:
    st.subheader("Officer Response Performance")
    st.caption(
        "Scores are computed from assigned events in the Astram dataset. "
        "Volume (40%) + Speed (40%) + High-priority handled (20%). "
        "Officers with fewer than 2 assigned events are excluded."
    )

    summary = officer_summary(df)
    if summary:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Officers Tracked", summary.get('total_officers', 0))
        c2.metric("Top Performer", str(summary.get('top_performer', 'N/A')))
        c3.metric("Average Score", summary.get('avg_score', 'N/A'))
        if summary.get('avg_response_mins') is not None:
            c4.metric("Avg Response (min)", summary['avg_response_mins'])

    scores = compute_officer_scores(df)

    if scores.empty:
        st.info("No officer assignment data found (assigned_to_police_id column empty or absent).")
    else:
        col1, col2 = st.columns([3, 2])

        with col1:
            display = scores[['rank', 'officer_id', 'total_events', 'total_score']].copy()
            if 'avg_response_mins' in scores.columns:
                display['avg_response_mins'] = scores['avg_response_mins']
            if 'high_priority_count' in scores.columns:
                display['high_priority_count'] = scores['high_priority_count']

            display = display.rename(columns={
                'rank': 'Rank',
                'officer_id': 'Officer ID',
                'total_events': 'Events',
                'total_score': 'Score',
                'avg_response_mins': 'Avg Response (min)',
                'high_priority_count': 'High Priority',
            })
            st.dataframe(display.head(20), use_container_width=True, hide_index=True)

        with col2:
            st.markdown("**Score Components**")
            st.markdown("""
            | Component | Weight | Based on |
            |---|---|---|
            | Volume | 40% | Events handled |
            | Speed | 40% | Avg response time |
            | Severity | 20% | High priority events |

            Note: Most events in the Astram dataset have no assigned officer (data is anonymized).
            In a live deployment, officer IDs would be populated for all active assignments.
            """)

            if len(scores) >= 3:
                top = scores.head(8).sort_values('total_score')
                fig = px.bar(top, x='total_score', y=top['officer_id'].astype(str),
                             orientation='h', color_discrete_sequence=['#1a3a5c'],
                             labels={'total_score': 'Score', 'y': 'Officer'})
                fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=260,
                                  title='Officer Rankings')
                st.plotly_chart(fig, use_container_width=True)

# --- Reporter scores ---
with tab2:
    st.subheader("Citizen Reporter Points")
    st.caption(
        "10 points per verified report. Verification triggers automatically when 3+ reports "
        "arrive from the same area. The board below shows demo data plus any reports submitted "
        "in this session via the Citizen Reports page."
    )

    session_reports = get_all_reports()
    session_count = len(session_reports) if not session_reports.empty else 0

    board = get_leaderboard()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Reporters", len(board))
    c2.metric("Reports this session", session_count)
    c3.metric("Points available per report", "10 (when verified)")

    col1, col2 = st.columns([3, 2])

    with col1:
        display_board = board.rename(columns={
            'reporter_id': 'Reporter ID',
            'rank': 'Rank',
            'reports_submitted': 'Reports',
            'verified_reports': 'Verified',
            'total_points': 'Points',
        })
        st.dataframe(display_board, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("**How points work**")
        st.markdown("""
        | Action | Points |
        |---|---|
        | Report auto-verified | 10 |
        | Unverified report | 0 |

        Auto-verification fires when 3+ reports
        land within ~200m of each other.

        **Future additions:**
        - Accuracy bonus if report matches an Astram log
        - Streak multiplier for consistent reporters
        - Badge system for top reporters
        """)

        if len(board) > 0:
            top5 = board.head(5)
            fig2 = px.bar(top5, x='total_points', y=top5['reporter_id'].astype(str),
                          orientation='h', color_discrete_sequence=['#1a3a5c'],
                          labels={'total_points': 'Points', 'y': 'Reporter'})
            fig2.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=220,
                               title='Top 5 Reporters')
            st.plotly_chart(fig2, use_container_width=True)
