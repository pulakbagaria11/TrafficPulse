import pandas as pd
import numpy as np


def compute_officer_scores(df):
    id_col = None
    for c in ['assigned_to_police_id', 'officer_id', 'police_id', 'assigned_officer']:
        if c in df.columns:
            id_col = c
            break

    if not id_col:
        return pd.DataFrame()

    assigned = df[df[id_col].notna()].copy()
    if assigned.empty:
        return pd.DataFrame()

    agg = {
        'total_events': (id_col, 'count'),
    }
    if 'priority_enc' in assigned.columns:
        agg['high_priority_count'] = ('priority_enc', 'sum')
    if 'closure_enc' in assigned.columns:
        agg['closures_required'] = ('closure_enc', 'sum')

    scores = (
        assigned.groupby(id_col)
        .agg(**agg)
        .reset_index()
        .rename(columns={id_col: 'officer_id'})
    )

    if 'duration_mins' in assigned.columns:
        resp = (
            assigned[assigned['duration_mins'].notna()]
            .groupby(id_col)['duration_mins']
            .mean()
            .reset_index()
            .rename(columns={id_col: 'officer_id', 'duration_mins': 'avg_response_mins'})
        )
        scores = scores.merge(resp, on='officer_id', how='left')

    scores = scores[scores['total_events'] >= 2]

    max_events = scores['total_events'].max() or 1
    scores['volume_score'] = (scores['total_events'] / max_events * 40).round(1)

    if 'avg_response_mins' in scores.columns:
        scores['avg_response_mins'] = scores['avg_response_mins'].round(1)
        max_resp = scores['avg_response_mins'].replace(0, np.nan).max() or 1
        scores['speed_score'] = (
            (1 - scores['avg_response_mins'].fillna(max_resp) / max_resp) * 40
        ).clip(0, 40).round(1)
    else:
        scores['speed_score'] = 20.0

    if 'high_priority_count' in scores.columns:
        scores['high_priority_count'] = scores['high_priority_count'].fillna(0).astype(int)
        max_hp = scores['high_priority_count'].max() or 1
        scores['severity_score'] = (scores['high_priority_count'] / max_hp * 20).round(1)
    else:
        scores['severity_score'] = 10.0

    scores['total_score'] = (
        scores['volume_score'] + scores['speed_score'] + scores['severity_score']
    ).round(1)

    scores = scores.sort_values('total_score', ascending=False).reset_index(drop=True)
    scores['rank'] = range(1, len(scores) + 1)

    return scores


def officer_summary(df):
    scores = compute_officer_scores(df)
    if scores.empty:
        return {}
    return {
        'total_officers': len(scores),
        'top_performer': str(scores.iloc[0]['officer_id']) if len(scores) > 0 else 'N/A',
        'avg_score': round(float(scores['total_score'].mean()), 1),
        'avg_response_mins': round(float(scores['avg_response_mins'].mean()), 1)
        if 'avg_response_mins' in scores.columns else None,
    }
