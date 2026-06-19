"""
Diversion routing module.

Mappls routing REST API calls are blocked server-side by CloudFront IP restriction
(the domain whitelist applies to client-side JS, not Python backends).
Routing is therefore handled via:
  1. mappls.direction() JavaScript plugin embedded in the map HTML (client-side, works)
  2. Corridor-based alternate suggestions derived from the Astram dataset (no API needed)
"""

CORRIDOR_ALTERNATES = {
    'Tumkur Road':          ['Bellary Road', 'Outer Ring Road West'],
    'Mysore Road':          ['Bannerghatta Road', 'Kanakapura Road'],
    'Bellary Road':         ['Tumkur Road', 'Outer Ring Road North'],
    'Outer Ring Road':      ['NICE Road', 'Hosur Road'],
    'Hosur Road':           ['Sarjapur Road', 'Old Madras Road'],
    'Sarjapur Road':        ['Hosur Road', 'Marathahalli–Sarjapur Road'],
    'Bannerghatta Road':    ['Kanakapura Road', 'Mysore Road'],
    'MG Road':              ['Residency Road', 'Brigade Road'],
    'Residency Road':       ['MG Road', 'Cunningham Road'],
    'Old Madras Road':      ['New BEL Road', 'Outer Ring Road East'],
    'Marathahalli':         ['Sarjapur Road', 'Outer Ring Road East'],
    'Electronic City':      ['Hosur Road alt', 'Bannerghatta Road'],
    'Hebbal':               ['Bellary Road', 'Outer Ring Road North'],
    'Yeshwanthpur':         ['Tumkur Road alt', 'Rajajinagar Main Road'],
}


def get_corridor_alternates(corridor):
    if not corridor:
        return []
    corridor_lower = str(corridor).lower()
    for key, alts in CORRIDOR_ALTERNATES.items():
        if key.lower() in corridor_lower or corridor_lower in key.lower():
            return alts
    # Generic fallback
    return ['Outer Ring Road', 'NICE Road corridor']


def get_route(origin_lat, origin_lon, dest_lat, dest_lon):
    """
    Returns None — routing is done client-side via Mappls JS SDK.
    This stub keeps imports in pages intact.
    """
    return None, "Routing via Mappls JS SDK (client-side). See the map below."
