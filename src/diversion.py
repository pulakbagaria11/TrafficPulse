import requests
import streamlit as st

MAPPLS_ROUTE_URL = (
    "https://apis.mappls.com/advancedmaps/v1/{key}/route_adv/driving/"
    "{olon},{olat};{dlon},{dlat}"
)

MAPPLS_GEOCODE_URL = (
    "https://apis.mappls.com/advancedmaps/v1/{key}/geo_code"
)


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

    url = MAPPLS_ROUTE_URL.format(
        key=key,
        olat=origin_lat, olon=origin_lon,
        dlat=dest_lat, dlon=dest_lon,
    )
    params = {
        'region': 'IND',
        'alternatives': 'true',
        'steps': 'false',
        'overview': 'simplified',
    }

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        routes = data.get('routes', [])
        if not routes:
            return None, "No routes found."

        results = []
        for r in routes[:3]:
            legs = r.get('legs', [{}])
            distance_km = round(legs[0].get('distance', 0) / 1000, 1)
            duration_min = round(legs[0].get('duration', 0) / 60, 1)
            results.append({
                'distance_km': distance_km,
                'duration_min': duration_min,
                'summary': r.get('summary', 'Alternate route'),
            })
        return results, None

    except requests.exceptions.RequestException as e:
        return None, f"Routing API error: {str(e)}"


def geocode_address(address):
    key = _get_key()
    if not key:
        return None

    url = MAPPLS_GEOCODE_URL.format(key=key)
    params = {'addr': address, 'region': 'IND'}

    try:
        resp = requests.get(url, params=params, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        results = data.get('copResults', {})
        if results:
            lat = float(results.get('latitude', 0))
            lon = float(results.get('longitude', 0))
            return {'lat': lat, 'lon': lon, 'formatted': results.get('formattedAddress', address)}
    except Exception:
        pass
    return None


def suggest_diversion(event_lat, event_lon, corridor=None):
    bengaluru_center = (12.9716, 77.5946)
    routes, err = get_route(
        event_lat - 0.01, event_lon - 0.01,
        event_lat + 0.01, event_lon + 0.01,
    )
    if err:
        return None, err
    return routes, None
