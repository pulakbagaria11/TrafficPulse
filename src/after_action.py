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
    """Vectorized over the whole closed-events frame -- a row-by-row
    predict_event() loop here took 10s+ on ~3k events (rebuilding a
    1-row DataFrame and calling predict_proba per row), making the
    After-Action page stall on every load/filter change."""
    from src.severity_model import CAT_COLS

    closed = get_closed_events(df)
    if closed.empty or 'priority_enc' not in closed.columns or 'priority' not in models:
        return pd.DataFrame()
    closed = closed.dropna(subset=['priority_enc'])
    if closed.empty:
        return pd.DataFrame()

    feat = closed.copy()
    for c in CAT_COLS:
        if c in feat.columns and c in encoders:
            le = encoders[c]
            known = feat[c].fillna('unknown').astype(str)
            mask = known.isin(le.classes_)
            encoded = pd.Series(-1, index=feat.index)
            encoded[mask] = le.transform(known[mask])
            feat[c + '_enc'] = encoded

    X = feat.reindex(columns=feature_cols).fillna(-1)
    probs = models['priority']['model'].predict_proba(X)[:, 1]
    predicted_high = (probs >= 0.5).astype(int)

    result = pd.DataFrame({
        'event_cause': closed['event_cause'].values if 'event_cause' in closed.columns else None,
        'month': closed['month'].values if 'month' in closed.columns else None,
        'actual_priority': closed['priority_enc'].astype(int).values,
        'predicted_priority_prob': probs,
        'predicted_high': predicted_high,
        'duration_mins': closed['duration_mins'].values if 'duration_mins' in closed.columns else None,
    })
    result['correct'] = result['actual_priority'] == result['predicted_high']
    return result


def accuracy_by_month(df, models, encoders, feature_cols):
    """Accuracy of the existing (fixed, trained-once) model evaluated
    separately per month -- the simplest honest signal for whether
    accuracy is drifting over time since training, i.e. whether a
    periodic retrain is warranted."""
    acc_df = accuracy_by_cause(df, models, encoders, feature_cols)
    if acc_df.empty or 'month' not in acc_df.columns:
        return pd.DataFrame()

    month_names = {11: 'Nov', 12: 'Dec', 1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr'}
    chrono_order = {11: 0, 12: 1, 1: 2, 2: 3, 3: 4, 4: 5}
    result = (
        acc_df.groupby('month')
        .agg(accuracy=('correct', 'mean'), count=('correct', 'count'))
        .reset_index()
    )
    result['sort_key'] = result['month'].map(chrono_order)
    result = result.sort_values('sort_key').drop(columns='sort_key')
    result['month_name'] = result['month'].map(month_names)
    result['accuracy_pct'] = (result['accuracy'] * 100).round(1)
    result['split'] = result['month'].apply(
        lambda m: 'Train (in-sample)' if m in (11, 12, 1, 2) else 'Test (held-out)'
    )
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
