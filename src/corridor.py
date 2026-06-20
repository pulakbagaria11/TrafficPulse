import pandas as pd
import numpy as np


def get_corridor_stats(df, top_n=20):
    if 'corridor' not in df.columns:
        return pd.DataFrame()

    d = df[df['corridor'].notna()].copy()
    if d.empty:
        return pd.DataFrame()

    agg = {'incidents': ('latitude', 'count')}
    if 'priority_enc' in d.columns:
        agg['high_priority'] = ('priority_enc', 'sum')
    if 'closure_enc' in d.columns:
        agg['road_closures'] = ('closure_enc', 'sum')
    if 'duration_mins' in d.columns:
        agg['avg_duration_mins'] = ('duration_mins', 'mean')

    stats = (
        d.groupby('corridor')
        .agg(**agg)
        .reset_index()
        .sort_values('incidents', ascending=False)
        .head(top_n)
    )

    if 'high_priority' in stats.columns:
        stats['high_priority_rate_pct'] = (
            stats['high_priority'] / stats['incidents'] * 100
        ).round(1)
    if 'road_closures' in stats.columns:
        stats['closure_rate_pct'] = (
            stats['road_closures'] / stats['incidents'] * 100
        ).round(1)
    if 'avg_duration_mins' in stats.columns:
        stats['avg_duration_mins'] = stats['avg_duration_mins'].round(1)

    return stats.reset_index(drop=True)


def get_monthly_trend(df):
    if 'start_datetime' not in df.columns or 'month' not in df.columns:
        return pd.DataFrame()

    agg = {'incidents': ('latitude', 'count')}
    if 'priority_enc' in df.columns:
        agg['high_priority'] = ('priority_enc', 'sum')

    trend = (
        df.groupby('month')
        .agg(**agg)
        .reset_index()
    )

    month_names = {
        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May',
        6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct',
        11: 'Nov', 12: 'Dec',
    }
    trend['month_name'] = trend['month'].map(month_names)
    return trend.sort_values('month')


def get_weekday_trend(df):
    if 'weekday' not in df.columns:
        return pd.DataFrame()

    agg = {'incidents': ('latitude', 'count')}
    if 'priority_enc' in df.columns:
        agg['high_priority'] = ('priority_enc', 'sum')

    trend = (
        df.groupby('weekday')
        .agg(**agg)
        .reset_index()
    )
    day_names = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    trend['day'] = trend['weekday'].map(day_names)
    return trend.sort_values('weekday')
