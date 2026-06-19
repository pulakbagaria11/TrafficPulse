import pandas as pd
import numpy as np


def get_closed_events(df):
    if 'closed_datetime' not in df.columns or 'start_datetime' not in df.columns:
        return pd.DataFrame()
    return df[df['closed_datetime'].notna() & df['start_datetime'].notna()].copy()


def response_time_stats(df):
    closed = get_closed_events(df)
    if closed.empty or 'duration_mins' not in closed.columns:
        return {}

    d = closed['duration_mins'].dropna()
    return {
        'count': int(len(d)),
        'mean_mins': round(float(d.mean()), 1),
        'median_mins': round(float(d.median()), 1),
        'p90_mins': round(float(d.quantile(0.9)), 1),
        'fastest_mins': round(float(d.min()), 1),
    }


def accuracy_by_cause(df, models, encoders, feature_cols):
    from src.severity_model import predict_event

    closed = get_closed_events(df)
    if closed.empty or 'priority_enc' not in closed.columns:
        return pd.DataFrame()

    rows = []
    for _, row in closed.iterrows():
        try:
            preds = predict_event(
                models, encoders, feature_cols,
                event_cause=str(row.get('event_cause', 'unknown')),
                event_type=str(row.get('event_type', 'unknown')),
                lat=float(row.get('latitude', 12.97)),
                lon=float(row.get('longitude', 77.59)),
                hour=int(row.get('hour', 8)),
                weekday=int(row.get('weekday', 0)),
                month=int(row.get('month', 1)),
            )
            rows.append({
                'event_cause': row.get('event_cause'),
                'actual_priority': int(row.get('priority_enc', 0)),
                'predicted_priority_prob': preds.get('priority', 0),
                'predicted_high': 1 if preds.get('priority', 0) >= 0.5 else 0,
                'duration_mins': row.get('duration_mins'),
                'correct': int(row.get('priority_enc', 0)) == (1 if preds.get('priority', 0) >= 0.5 else 0),
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    return result


def summary_by_cause(df):
    closed = get_closed_events(df)
    if closed.empty:
        return pd.DataFrame()

    cols = {'duration_mins': 'median', 'priority_enc': 'mean', 'closure_enc': 'mean'}
    agg_cols = {k: v for k, v in cols.items() if k in closed.columns}

    summary = (
        closed.groupby('event_cause')
        .agg(**{
            'event_count': ('latitude', 'count'),
            **{k: (k, v) for k, v in agg_cols.items()},
        })
        .reset_index()
        .sort_values('event_count', ascending=False)
    )

    if 'duration_mins' in summary.columns:
        summary['duration_mins'] = summary['duration_mins'].round(1)
    if 'priority_enc' in summary.columns:
        summary = summary.rename(columns={'priority_enc': 'high_priority_rate'})
        summary['high_priority_rate'] = summary['high_priority_rate'].round(2)
    if 'closure_enc' in summary.columns:
        summary = summary.rename(columns={'closure_enc': 'closure_rate'})
        summary['closure_rate'] = summary['closure_rate'].round(2)

    return summary
