import pandas as pd

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
