"""
Emergency corridor advisory.

Identifies the nearest junction to hold cross-traffic at, and an ETA
for emergency vehicles from the nearest major hospital, using Mappls'
real road ETA where available.
"""
from src import mappls_rest

# Reference coordinates for major Bengaluru hospitals -- used only as
# "nearest emergency response point" anchors for ETA estimation, not as
# a competing incident/traffic dataset.
EMERGENCY_HUBS = {
    'Victoria Hospital (KR Market)': (12.9634, 77.5746),
    "St. John's Medical College Hospital (Koramangala)": (12.9279, 77.6271),
    'Manipal Hospital (Old Airport Road)': (12.9591, 77.6473),
    'Narayana Health City (Bommasandra)': (12.8049, 77.6938),
    'Fortis Hospital (Bannerghatta Road)': (12.8838, 77.5963),
    'Vydehi Hospital (Whitefield)': (12.9698, 77.7547),
    'Columbia Asia Hospital (Hebbal)': (13.0455, 77.5973),
    'BGS Gleneagles Global Hospital (Kengeri)': (12.9081, 77.4847),
    'M.S. Ramaiah Memorial Hospital (MSRIT)': (13.0297, 77.5663),
    'Apollo Hospital (Seshadripuram)': (12.9959, 77.5770),
}

# Causes where emergency-vehicle access matters even when the historical
# cause-average severity (calibrate_tiers) doesn't reach High/Critical.
EMERGENCY_TRIGGER_CAUSES = {'accident', 'vip_movement', 'tree_fall', 'protest', 'fog_visibility'}


def _nearest_hub(lat, lon):
    best_name, best_coord, best_dist = None, None, float('inf')
    for name, coord in EMERGENCY_HUBS.items():
        dist = (coord[0] - lat) ** 2 + (coord[1] - lon) ** 2
        if dist < best_dist:
            best_dist, best_name, best_coord = dist, name, coord
    return best_name, best_coord


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


def should_trigger(cause, rec):
    if rec.get('tier') in ('Critical', 'High'):
        return True
    if cause in EMERGENCY_TRIGGER_CAUSES and (rec.get('supervisor') or rec.get('barricades', 0) >= 4):
        return True
    return False


def get_emergency_advisory(df, lat, lon, cause, rec):
    if not should_trigger(cause, rec):
        return None

    hub_name, hub_coord = _nearest_hub(lat, lon)
    junction = _nearest_junction(df, lat, lon) or "the nearest signal-controlled junction"

    eta_mins = 6  # sane default if Mappls ETA is unavailable
    if hub_coord:
        result = mappls_rest.distance_matrix(hub_coord, (lat, lon))
        if result:
            eta_mins = max(1, round(result['duration_s'] / 60))

    return {
        'hub': hub_name or 'nearest response unit',
        'junction': junction,
        'eta_mins': eta_mins,
    }
