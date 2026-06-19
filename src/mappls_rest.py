"""
Mappls REST API client (Geocode, Distance Matrix, Direction).

Separate from the Mappls Maps SDK (which this account cannot use for
tile-serving) -- these are server-side REST calls authenticated via
OAuth2 client_credentials, and work independently of that block.

All public functions return None on any failure (network, auth, quota)
so callers can degrade gracefully instead of crashing the page.
"""
import requests
import streamlit as st

TOKEN_URL = "https://outpost.mappls.com/api/security/oauth/token"
GEOCODE_URL = "https://atlas.mappls.com/api/places/geocode"
ROUTE_URL_TMPL = "https://apis.mappls.com/advancedmaps/v1/{token}/route_adv/driving/{coords}"
MATRIX_URL_TMPL = "https://apis.mappls.com/advancedmaps/v1/{token}/distance_matrix/driving/{coords}"

TIMEOUT = 6


@st.cache_resource(ttl=82800)  # ~23h, just under the token's 24h expiry
def _get_token():
    try:
        creds = st.secrets["mappls"]
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception:
        return None


def _decode_polyline(encoded, precision=5):
    """Decode a Google-format encoded polyline into a list of (lat, lon)."""
    factor = 10 ** precision
    coords = []
    index = lat = lon = 0
    length = len(encoded)

    while index < length:
        for is_lat in (True, False):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if is_lat:
                lat += delta
            else:
                lon += delta
        coords.append((lat / factor, lon / factor))

    return coords


@st.cache_data(ttl=3600, show_spinner=False)
def geocode(address):
    token = _get_token()
    if not token:
        return None
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"address": address},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json().get("copResults")
        if not result:
            return None
        return {
            "formatted_address": result.get("formattedAddress"),
            "eloc": result.get("eLoc"),
        }
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def distance_matrix(origin, dest):
    """origin/dest are (lat, lon) tuples. Returns {distance_m, duration_s} or None."""
    token = _get_token()
    if not token:
        return None
    coords = f"{origin[1]:.6f},{origin[0]:.6f};{dest[1]:.6f},{dest[0]:.6f}"
    try:
        resp = requests.get(
            MATRIX_URL_TMPL.format(token=token, coords=coords), timeout=TIMEOUT
        )
        resp.raise_for_status()
        results = resp.json().get("results", {})
        distances = results.get("distances")
        durations = results.get("durations")
        if not distances or not durations:
            return None
        return {"distance_m": distances[0][1], "duration_s": durations[0][1]}
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_route(origin, dest):
    """origin/dest are (lat, lon) tuples. Returns list of (lat, lon) or None."""
    token = _get_token()
    if not token:
        return None
    coords = f"{origin[1]:.6f},{origin[0]:.6f};{dest[1]:.6f},{dest[0]:.6f}"
    try:
        resp = requests.get(
            ROUTE_URL_TMPL.format(token=token, coords=coords),
            params={"geometries": "polyline", "overview": "full"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        routes = resp.json().get("routes")
        if not routes:
            return None
        geometry = routes[0].get("geometry")
        if not geometry:
            return None
        return _decode_polyline(geometry)
    except Exception:
        return None
