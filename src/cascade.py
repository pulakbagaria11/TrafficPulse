"""
Cascade predictor — models second-order congestion on adjacent corridors.

For each corridor -> alternate pair in CORRIDOR_ALTERNATES, measures how
often an incident on the alternate follows an incident on the source
corridor within a short time window, versus the alternate's baseline
incident rate for an equivalent random window.
"""
import pandas as pd
import streamlit as st

from src.diversion import CORRIDOR_ALTERNATES


def _corridor_rows(df, corridor_name):
    if 'corridor' not in df.columns:
        return df.iloc[0:0]
    corridor_lower = str(corridor_name).lower()
    known = df[df['corridor'].notna()]
    mask = known['corridor'].str.lower().apply(
        lambda c: c in corridor_lower or corridor_lower in c
    )
    return known[mask]


@st.cache_data(show_spinner="Computing cascade risk...")
def compute_cascade_risk(df, window_hours=3):
    if 'start_datetime' not in df.columns:
        return pd.DataFrame()

    span = df['start_datetime'].max() - df['start_datetime'].min()
    total_hours = max(span.total_seconds() / 3600, 1)
    window = pd.Timedelta(hours=window_hours)

    rows = []
    for corridor, alts in CORRIDOR_ALTERNATES.items():
        source = _corridor_rows(df, corridor)
        if len(source) < 3:
            continue
        source_times = source['start_datetime'].dropna().sort_values()
        if source_times.empty:
            continue

        for alt in alts:
            alt_rows = _corridor_rows(df, alt)
            alt_times = alt_rows['start_datetime'].dropna().sort_values()
            if len(alt_times) < 3:
                continue

            followed = sum(
                ((alt_times > t) & (alt_times <= t + window)).any()
                for t in source_times
            )
            cascade_rate = followed / len(source_times)

            baseline_rate = min(1.0, len(alt_times) / total_hours * window_hours)
            uplift = round(cascade_rate / baseline_rate, 1) if baseline_rate > 0 else None

            rows.append({
                'corridor': corridor,
                'alt_corridor': alt,
                'window_hours': window_hours,
                'cascade_rate_pct': round(cascade_rate * 100, 1),
                'baseline_rate_pct': round(baseline_rate * 100, 1),
                'uplift_x': uplift,
            })

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    return result[result['uplift_x'].notna()].sort_values('uplift_x', ascending=False).reset_index(drop=True)


def top_cascade_for_corridor(df, corridor_name, min_uplift=1.5):
    risk = compute_cascade_risk(df)
    if risk.empty or not corridor_name:
        return None
    match = risk[risk['corridor'] == corridor_name]
    if match.empty or match.iloc[0]['uplift_x'] < min_uplift:
        return None
    return match.iloc[0].to_dict()
