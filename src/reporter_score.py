import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime

SESSION_KEY = 'citizen_reports'


def init_reports():
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = []


def submit_report(reporter_id, cause, lat, lon, description=''):
    init_reports()
    report = {
        'reporter_id': reporter_id,
        'cause': cause,
        'lat': lat,
        'lon': lon,
        'description': description,
        'verified': False,
        'points_awarded': 0,
        'submitted_at': datetime.now(),
    }
    st.session_state[SESSION_KEY].append(report)
    _check_auto_verify(lat, lon)
    return len(st.session_state[SESSION_KEY]) - 1


def _check_auto_verify(lat, lon, radius_deg=0.002, min_reports=3):
    reports = st.session_state.get(SESSION_KEY, [])
    nearby = [
        r for r in reports
        if abs(r['lat'] - lat) < radius_deg and abs(r['lon'] - lon) < radius_deg
    ]
    if len(nearby) >= min_reports:
        for r in nearby:
            if not r['verified']:
                r['verified'] = True
                r['points_awarded'] = 10


def get_leaderboard():
    init_reports()
    reports = st.session_state.get(SESSION_KEY, [])
    if not reports:
        return _demo_leaderboard()

    df = pd.DataFrame(reports)
    board = (
        df.groupby('reporter_id')
        .agg(
            reports_submitted=('cause', 'count'),
            verified_reports=('verified', 'sum'),
            total_points=('points_awarded', 'sum'),
        )
        .reset_index()
        .sort_values('total_points', ascending=False)
        .reset_index(drop=True)
    )
    board['rank'] = range(1, len(board) + 1)
    return board


def _demo_leaderboard():
    np.random.seed(42)
    ids = [f'CIT{i:04d}' for i in range(1, 21)]
    reports = np.random.randint(1, 30, 20)
    verified = (reports * np.random.uniform(0.4, 0.9, 20)).astype(int)
    points = verified * 10 + np.random.randint(0, 5, 20)

    df = pd.DataFrame({
        'reporter_id': ids,
        'reports_submitted': reports,
        'verified_reports': verified,
        'total_points': points,
    }).sort_values('total_points', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)
    return df


def get_all_reports():
    init_reports()
    return pd.DataFrame(st.session_state.get(SESSION_KEY, []))
