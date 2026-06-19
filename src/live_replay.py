"""
Live Replay -- replays the Astram incident history in timestamp order to
simulate a live feed (the "real-time" half of the problem statement,
since the dataset itself is historical). Always uses the full dataset,
independent of the page's other filters, so the chronological order is
never broken.
"""
import pandas as pd
import folium
from folium.plugins import HeatMap

STEP_OPTIONS = {
    '1 hour': pd.Timedelta(hours=1),
    '6 hours': pd.Timedelta(hours=6),
    '1 day': pd.Timedelta(days=1),
    '3 days': pd.Timedelta(days=3),
    '1 week': pd.Timedelta(weeks=1),
}


def initial_cursor(df):
    return df['start_datetime'].min() + step_to_timedelta('1 day')


def step_to_timedelta(step_label):
    return STEP_OPTIONS.get(step_label, pd.Timedelta(days=1))


def make_replay_map(df, cursor, step_label):
    from src.data_prep import BENGALURU_CENTER, cause_label

    step = step_to_timedelta(step_label)
    cumulative = df[df['start_datetime'] <= cursor]
    recent = cumulative[cumulative['start_datetime'] > cursor - step]

    m = folium.Map(location=BENGALURU_CENTER, zoom_start=11, tiles='CartoDB positron')

    heat_data = cumulative[['latitude', 'longitude']].dropna().values.tolist()
    if heat_data:
        HeatMap(heat_data, radius=12, blur=8, max_zoom=13).add_to(m)

    for _, row in recent.iterrows():
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=9, color='#c0392b', fill=True, fill_color='#ff0000', fill_opacity=0.9,
            tooltip=f"Just reported: {cause_label(str(row.get('event_cause', '')))} "
                    f"at {row['start_datetime'].strftime('%H:%M')}",
        ).add_to(m)

    return m


def replay_counts(df, cursor, step_label):
    step = step_to_timedelta(step_label)
    cumulative_count = int((df['start_datetime'] <= cursor).sum())
    recent_count = int(
        ((df['start_datetime'] <= cursor) & (df['start_datetime'] > cursor - step)).sum()
    )
    return cumulative_count, recent_count
