import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap
import streamlit as st

BENGALURU_CENTER = [12.9716, 77.5946]


def get_hotspot_grid(df, cause_filter=None, hour_range=None):
    d = df.copy()
    if cause_filter:
        d = d[d['event_cause'].isin(cause_filter)]
    if hour_range and 'hour' in d.columns:
        d = d[d['hour'].between(hour_range[0], hour_range[1])]

    grid = (
        d.groupby(['lat_grid', 'lon_grid'])
        .agg(
            incident_count=('latitude', 'count'),
            high_priority=('priority_enc', 'sum') if 'priority_enc' in d.columns else ('latitude', 'count'),
            road_closures=('closure_enc', 'sum') if 'closure_enc' in d.columns else ('latitude', 'count'),
        )
        .reset_index()
        .sort_values('incident_count', ascending=False)
    )
    return grid


def make_heatmap(df, cause_filter=None, hour_range=None, zoom=11):
    d = df.copy()
    if cause_filter:
        d = d[d['event_cause'].isin(cause_filter)]
    if hour_range and 'hour' in d.columns:
        d = d[d['hour'].between(hour_range[0], hour_range[1])]

    m = folium.Map(
        location=BENGALURU_CENTER,
        zoom_start=zoom,
        tiles='CartoDB positron',
    )

    heat_data = d[['latitude', 'longitude']].dropna().values.tolist()
    if heat_data:
        HeatMap(
            heat_data,
            radius=15,
            blur=10,
            max_zoom=13,
            gradient={0.2: '#ffffb2', 0.5: '#fd8d3c', 0.8: '#f03b20', 1.0: '#bd0026'},
        ).add_to(m)

    return m


def make_marker_map(df, max_markers=200, zoom=11):
    m = folium.Map(
        location=BENGALURU_CENTER,
        zoom_start=zoom,
        tiles='CartoDB positron',
    )

    sample = df.head(max_markers)
    for _, row in sample.iterrows():
        if pd.isna(row.get('latitude')) or pd.isna(row.get('longitude')):
            continue

        priority = str(row.get('priority', 'Low')).strip()
        color = 'red' if priority.lower() == 'high' else 'blue'

        cause = str(row.get('event_cause', '')).replace('_', ' ').title()
        popup_html = f"""
        <b>{cause}</b><br>
        Priority: {priority}<br>
        Time: {str(row.get('hour', ''))[:2]}:00
        """

        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=5,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=200),
        ).add_to(m)

    return m


def top_hotspots(df, n=10):
    grid = get_hotspot_grid(df)
    return grid.head(n)
