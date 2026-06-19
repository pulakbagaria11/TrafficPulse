"""
Flood-prone road flagging.

Same recurring-location pattern as tow_truck.py's breakdown hotspots,
filtered to water_logging incidents.
"""
import folium

FLOOD_CAUSES = ['water_logging']


def get_flood_prone_locations(df, min_incidents=2):
    fl = df[df['event_cause'].isin(FLOOD_CAUSES)].copy()
    if fl.empty:
        return fl.assign(incident_count=[])

    grid = (
        fl.groupby(['lat_grid', 'lon_grid'])
        .agg(
            incident_count=('latitude', 'count'),
            corridor=('corridor', lambda x: x.dropna().value_counts().index[0] if x.notna().any() else ''),
        )
        .reset_index()
    )
    grid = grid[grid['incident_count'] >= min_incidents]
    return grid.sort_values('incident_count', ascending=False).reset_index(drop=True)


def make_flood_map(df):
    from src.data_prep import BENGALURU_CENTER
    locations = get_flood_prone_locations(df)

    m = folium.Map(location=BENGALURU_CENTER, zoom_start=11, tiles='CartoDB positron')

    for _, row in locations.iterrows():
        radius = min(8 + row['incident_count'] / 3, 22)
        folium.CircleMarker(
            location=[row['lat_grid'], row['lon_grid']],
            radius=radius,
            color='#2980b9',
            fill=True,
            fill_color='#3498db',
            fill_opacity=0.6,
            popup=folium.Popup(
                f"<b>Flood-Prone Location</b><br>"
                f"Water-logging incidents: {int(row['incident_count'])}<br>"
                f"Corridor: {row.get('corridor') or 'Unknown'}",
                max_width=220,
            ),
            tooltip=f"Water-logging: {int(row['incident_count'])} incidents",
        ).add_to(m)

    return m
