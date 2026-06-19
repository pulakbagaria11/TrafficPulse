import requests
import streamlit as st

# Mappls REST routing endpoints (in order of preference)
_ROUTE_ETA = "https://apis.mappls.com/advancedmaps/v1/{key}/route_eta/driving/{olon},{olat};{dlon},{dlat}"
_ROUTE_ADV = "https://apis.mappls.com/advancedmaps/v1/{key}/route_adv/driving/{olon},{olat};{dlon},{dlat}"

# Alternate corridor suggestions derived from Bengaluru road network
# Used as a fallback when routing API is unavailable
CORRIDOR_ALTERNATES = {
    'Tumkur Road':       ['Bellary Road', 'Outer Ring Road (West)'],
    'Mysore Road':       ['Bannerghatta Road', 'Kanakapura Road'],
    'Bellary Road':      ['Tumkur Road', 'Outer Ring Road (North)'],
    'Outer Ring Road':   ['NICE Road', 'Hosur Road'],
    'Hosur Road':        ['Sarjapur Road', 'Outer Ring Road (South)'],
    'Sarjapur Road':     ['Hosur Road', 'Marathahalli-Sarjapur Road'],
    'Bannerghatta Road': ['Kanakapura Road', 'Mysore Road'],
    'MG Road':           ['Residency Road', 'Brigade Road'],
    'Residency Road':    ['MG Road', 'Cunningham Road'],
    'Old Madras Road':   ['New BEL Road', 'Outer Ring Road (East)'],
}


def _get_key():
    for accessor in [
        lambda: st.secrets["mappls"]["api_key"],
        lambda: st.secrets["MAPPLS_API_KEY"],
        lambda: st.secrets["api_key"],
    ]:
        try:
            key = accessor()
            if key:
                return str(key).strip()
        except Exception:
            continue
    return None


def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
    key = _get_key()
    if not key:
        return None, "Mappls API key not configured."

    params = {'region': 'IND', 'alternatives': 'true',
              'steps': 'false', 'overview': 'simplified'}

    for url_template in [_ROUTE_ETA, _ROUTE_ADV]:
        url = url_template.format(
            key=key,
            olat=origin_lat, olon=origin_lon,
            dlat=dest_lat, dlon=dest_lon,
        )
        try:
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get('routes', [])
                if routes:
                    results = []
                    for r in routes[:3]:
                        legs = r.get('legs', [{}])
                        results.append({
                            'distance_km': round(legs[0].get('distance', 0) / 1000, 1),
                            'duration_min': round(legs[0].get('duration', 0) / 60, 1),
                            'summary': r.get('summary', 'Alternate route'),
                        })
                    return results, None
            elif resp.status_code in (401, 403):
                return None, (
                    f"Mappls API key is expired or not authorized. "
                    f"Go to apis.mappls.com → My Apps, create a new app, "
                    f"and update the key in Streamlit Cloud Secrets."
                )
        except requests.exceptions.RequestException as e:
            continue

    return None, "Routing API unavailable."


def get_corridor_alternates(corridor):
    if not corridor:
        return []
    for key, alts in CORRIDOR_ALTERNATES.items():
        if key.lower() in corridor.lower():
            return alts
    return []


def suggest_diversion(event_lat, event_lon, corridor=None):
    routes, err = get_route(
        event_lat - 0.02, event_lon - 0.02,
        event_lat + 0.02, event_lon + 0.02,
    )
    return routes, err
