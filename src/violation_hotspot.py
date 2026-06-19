import pandas as pd
import numpy as np
import folium


REPEAT_THRESHOLD = 3
ESCALATE_THRESHOLD = 6


def get_violation_hotspots(df, min_incidents=3):
    grid = (
        df.groupby(['lat_grid', 'lon_grid'])
        .agg(
            incident_count=('latitude', 'count'),
            causes=('event_cause', lambda x: x.value_counts().index[0]),
            high_priority=('priority_enc', 'sum') if 'priority_enc' in df.columns else ('latitude', 'count'),
            last_seen=('start_datetime', 'max') if 'start_datetime' in df.columns else ('latitude', 'count'),
        )
        .reset_index()
    )

    grid = grid[grid['incident_count'] >= min_incidents].copy()
    grid['status'] = grid['incident_count'].apply(
        lambda n: 'Escalated' if n >= ESCALATE_THRESHOLD else 'Recurring'
    )
    grid['top_cause'] = grid['causes'].str.replace('_', ' ').str.title()

    if 'last_seen' in grid.columns:
        grid['last_seen'] = grid['last_seen'].astype(str).str[:16]

    return grid.sort_values('incident_count', ascending=False).reset_index(drop=True)


def make_violation_map(df):
    from src.data_prep import BENGALURU_CENTER
    hotspots = get_violation_hotspots(df)

    m = folium.Map(
        location=BENGALURU_CENTER,
        zoom_start=11,
        tiles='CartoDB positron',
    )

    for _, row in hotspots.iterrows():
        color = '#8e44ad' if row['status'] == 'Escalated' else '#e67e22'
        radius = min(6 + row['incident_count'] / 3, 22)

        popup_html = (
            f"<b>{row['top_cause']}</b><br>"
            f"Incidents: {int(row['incident_count'])}<br>"
            f"Status: <b>{row['status']}</b>"
        )

        folium.CircleMarker(
            location=[row['lat_grid'], row['lon_grid']],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.65,
            popup=folium.Popup(popup_html, max_width=220),
            tooltip=f"{row['status']}: {int(row['incident_count'])} incidents",
        ).add_to(m)

    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                padding:10px 14px;border-radius:6px;border:1px solid #ccc;font-size:13px;">
        <b>Status</b><br>
        <span style="color:#8e44ad;">&#9679;</span> Escalated (6+ incidents)<br>
        <span style="color:#e67e22;">&#9679;</span> Recurring (3-5 incidents)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


def escalation_summary(df):
    hotspots = get_violation_hotspots(df)
    if hotspots.empty:
        return {}
    return {
        'total_hotspots': len(hotspots),
        'escalated': int((hotspots['status'] == 'Escalated').sum()),
        'recurring': int((hotspots['status'] == 'Recurring').sum()),
        'worst_location': (
            f"{hotspots.iloc[0]['lat_grid']:.2f}, {hotspots.iloc[0]['lon_grid']:.2f}"
            if len(hotspots) > 0 else 'N/A'
        ),
    }
