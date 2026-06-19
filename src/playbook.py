import pandas as pd
import numpy as np


def build_playbook(df):
    group_cols = ['event_cause']
    if 'priority' in df.columns:
        group_cols.append('priority')

    agg = {}
    if 'duration_mins' in df.columns:
        agg['median_duration_mins'] = ('duration_mins', 'median')
    agg['event_count'] = ('latitude', 'count')
    if 'closure_enc' in df.columns:
        agg['closure_rate'] = ('closure_enc', 'mean')
    if 'is_peak_hour' in df.columns:
        agg['peak_hour_rate'] = ('is_peak_hour', 'mean')

    playbook = (
        df.groupby(group_cols)
        .agg(**agg)
        .reset_index()
        .sort_values('event_count', ascending=False)
    )

    if 'median_duration_mins' in playbook.columns:
        playbook['median_duration_mins'] = playbook['median_duration_mins'].round(1)
    if 'closure_rate' in playbook.columns:
        playbook['closure_rate'] = (playbook['closure_rate'] * 100).round(1)
    if 'peak_hour_rate' in playbook.columns:
        playbook['peak_hour_rate'] = (playbook['peak_hour_rate'] * 100).round(1)

    return playbook


def lookup(df, event_cause, priority=None):
    pb = build_playbook(df)
    result = pb[pb['event_cause'] == event_cause]
    if priority and 'priority' in pb.columns:
        result = result[result['priority'].str.lower() == priority.lower()]
    if result.empty:
        return None
    return result.iloc[0].to_dict()


def top_causes_by_time(df, hour_start, hour_end):
    if 'hour' not in df.columns:
        return pd.DataFrame()
    subset = df[df['hour'].between(hour_start, hour_end)]
    return (
        subset['event_cause']
        .value_counts()
        .head(5)
        .reset_index()
        .rename(columns={'count': 'incident_count', 'event_cause': 'cause'})
    )
