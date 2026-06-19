import pandas as pd
import numpy as np
from geopy.distance import geodesic
import folium
import streamlit as st

BREAKDOWN_CAUSES = ['vehicle_breakdown', 'breakdown']


def get_breakdown_hotspots(df, top_n=20):
    bd = df[df['event_cause'].isin(BREAKDOWN_CAUSES)].copy()
    if bd.empty:
        return pd.DataFrame()

    grid = (
        bd.groupby(['lat_grid', 'lon_grid'])
        .agg(
            breakdown_count=('latitude', 'count'),
            peak_hour=('hour', lambda x: int(x.mode().iloc[0]) if not x.empty and len(x.mode()) > 0 else 0),
        )
        .reset_index()
        .sort_values('breakdown_count', ascending=False)
        .head(top_n)
    )
    grid['rank'] = range(1, len(grid) + 1)
    return grid


def nearest_dispatch(incident_lat, incident_lon, truck_locations):
    if not truck_locations:
        return None, None

    best_dist = float('inf')
    best_truck = None
    for truck in truck_locations:
        dist = geodesic(
            (incident_lat, incident_lon),
            (truck['lat'], truck['lon'])
        ).km
        if dist < best_dist:
            best_dist = dist
            best_truck = truck

    return best_truck, round(best_dist, 2)


def preposition_recommendations(df):
    hotspots = get_breakdown_hotspots(df, top_n=10)
    if hotspots.empty:
        return []

    recs = []
    for _, row in hotspots.iterrows():
        hour = int(row.get('peak_hour', 8))
        if 7 <= hour <= 10:
            period = 'Morning peak (07:00-10:00)'
        elif 17 <= hour <= 20:
            period = 'Evening peak (17:00-20:00)'
        else:
            period = f'Around {hour:02d}:00'

        recs.append({
            'lat': row['lat_grid'],
            'lon': row['lon_grid'],
            'breakdowns': int(row['breakdown_count']),
            'deploy_during': period,
            'trucks_recommended': 1 if row['breakdown_count'] < 20 else 2,
        })
    return recs


def make_breakdown_map(df):
    from src.data_prep import BENGALURU_CENTER
    hotspots = get_breakdown_hotspots(df, top_n=20)

    m = folium.Map(
        location=BENGALURU_CENTER,
        zoom_start=11,
        tiles='CartoDB positron',
    )

    for _, row in hotspots.iterrows():
        radius = min(8 + row['breakdown_count'] / 5, 20)
        folium.CircleMarker(
            location=[row['lat_grid'], row['lon_grid']],
            radius=radius,
            color='#c0392b',
            fill=True,
            fill_color='#e74c3c',
            fill_opacity=0.6,
            popup=folium.Popup(
                f"<b>Breakdown Hotspot</b><br>Count: {int(row['breakdown_count'])}<br>"
                f"Peak hour: {int(row['peak_hour']):02d}:00",
                max_width=200,
            ),
            tooltip=f"Breakdowns: {int(row['breakdown_count'])}",
        ).add_to(m)

    return m
