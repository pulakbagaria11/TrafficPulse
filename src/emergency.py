"""
Emergency corridor advisory.

For Critical-tier incidents, identifies the nearest junction to hold
cross-traffic at and an ETA for emergency vehicles, using a per-zone
response-hub centroid and Mappls' real road ETA where available.
"""
from src import mappls_rest


def _zone_hubs(df):
    if 'zone' not in df.columns:
        return {}
    hubs = (
        df[df['zone'].notna()]
        .groupby('zone')[['latitude', 'longitude']]
        .mean()
    )
    return {zone: (row['latitude'], row['longitude']) for zone, row in hubs.iterrows()}


def _nearest_zone(df, lat, lon):
    hubs = _zone_hubs(df)
    if not hubs:
        return None, None
    best_zone, best_coord, best_dist = None, None, float('inf')
    for zone, coord in hubs.items():
        dist = (coord[0] - lat) ** 2 + (coord[1] - lon) ** 2
        if dist < best_dist:
            best_dist, best_zone, best_coord = dist, zone, coord
    return best_zone, best_coord


def _nearest_junction(df, lat, lon, radius_deg=0.03):
    if 'junction' not in df.columns:
        return None
    nearby = df[
        df['junction'].notna() &
        (df['latitude'] - lat).abs().lt(radius_deg) &
        (df['longitude'] - lon).abs().lt(radius_deg)
    ]
    if nearby.empty:
        return None
    return nearby['junction'].value_counts().index[0]


def get_emergency_advisory(df, lat, lon, tier):
    if tier != 'Critical':
        return None

    zone, hub_coord = _nearest_zone(df, lat, lon)
    junction = _nearest_junction(df, lat, lon)
    if not junction:
        junction = "the nearest signal-controlled junction"

    eta_mins = 6  # sane default if Mappls ETA is unavailable
    if hub_coord:
        result = mappls_rest.distance_matrix(hub_coord, (lat, lon))
        if result:
            eta_mins = max(1, round(result['duration_s'] / 60))

    return {
        'zone': zone or 'nearest response unit',
        'junction': junction,
        'eta_mins': eta_mins,
    }
