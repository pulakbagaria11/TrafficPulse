import pandas as pd
import streamlit as st

SEVERITY_TIERS = [
    {
        'tier': 'Critical',
        'min_priority_prob': 0.80,
        'min_closure_prob': 0.60,
        'personnel': 8,
        'barricades': 6,
        'diversion': True,
        'supervisor': True,
        'response_minutes': 5,
    },
    {
        'tier': 'High',
        'min_priority_prob': 0.60,
        'min_closure_prob': 0.30,
        'personnel': 5,
        'barricades': 4,
        'diversion': True,
        'supervisor': False,
        'response_minutes': 10,
    },
    {
        'tier': 'Medium',
        'min_priority_prob': 0.40,
        'min_closure_prob': 0.10,
        'personnel': 3,
        'barricades': 2,
        'diversion': False,
        'supervisor': False,
        'response_minutes': 15,
    },
    {
        'tier': 'Low',
        'min_priority_prob': 0.0,
        'min_closure_prob': 0.0,
        'personnel': 1,
        'barricades': 0,
        'diversion': False,
        'supervisor': False,
        'response_minutes': 30,
    },
]

CAUSE_ADJUSTMENTS = {
    'vip_movement': {'personnel': +4, 'barricades': +4, 'diversion': True, 'supervisor': True},
    'public_event': {'personnel': +2, 'barricades': +2},
    'procession': {'personnel': +2, 'barricades': +2},
    'accident': {'personnel': +1, 'response_minutes': -5},
}


def get_recommendation(priority_prob, closure_prob, event_cause=''):
    tier = SEVERITY_TIERS[-1]
    for t in SEVERITY_TIERS:
        if priority_prob >= t['min_priority_prob'] and closure_prob >= t['min_closure_prob']:
            tier = t
            break

    rec = dict(tier)
    adj = CAUSE_ADJUSTMENTS.get(event_cause, {})
    for k, v in adj.items():
        if k in rec:
            if isinstance(v, bool):
                rec[k] = rec[k] or v
            else:
                rec[k] = max(0, rec[k] + v)

    rec['priority_prob'] = round(priority_prob, 2)
    rec['closure_prob'] = round(closure_prob, 2)
    return rec


@st.cache_data(show_spinner=False)
def calibrate_tiers(df):
    if 'priority_enc' not in df.columns:
        return {}

    result = {}
    for cause, group in df.groupby('event_cause'):
        high_rate = group['priority_enc'].mean()
        closure_rate = group['closure_enc'].mean() if 'closure_enc' in group.columns else 0
        avg_duration = group['duration_mins'].median() if 'duration_mins' in group.columns else None
        result[cause] = {
            'high_priority_rate': round(float(high_rate), 2),
            'closure_rate': round(float(closure_rate), 2),
            'median_duration_mins': round(float(avg_duration), 1) if avg_duration is not None else None,
        }
    return result


# (lower bound, upper bound, extra personnel, extra barricades) for
# planned events (festivals, rallies, sports) sized by expected attendance.
CROWD_BANDS = [
    (0, 1000, 0, 0),
    (1000, 5000, 3, 2),
    (5000, 20000, 8, 6),
    (20000, 50000, 15, 12),
    (50000, float('inf'), 25, 20),
]


def scale_for_crowd_size(rec, attendance):
    """Scale a recommendation up for a planned event's expected attendance."""
    if not attendance or attendance <= 0:
        return rec

    scaled = dict(rec)
    for lo, hi, extra_personnel, extra_barricades in CROWD_BANDS:
        if lo <= attendance < hi:
            scaled['personnel'] = rec['personnel'] + extra_personnel
            scaled['barricades'] = rec['barricades'] + extra_barricades
            if attendance >= 5000:
                scaled['diversion'] = True
                scaled['supervisor'] = True
            if attendance >= 20000:
                scaled['response_minutes'] = max(3, rec['response_minutes'] - 5)
            break

    scaled['crowd_attendance'] = attendance
    return scaled
