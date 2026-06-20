"""
Diversion routing module.

Suggests alternate corridors using historical Astram corridor data,
and renders real road-snapped routes via the Mappls REST routing API
(src/mappls_rest.py) for the congested vs. alternate path.
"""

# Keyed on the corridor names actually present in the Astram dataset
# (verified against df['corridor'].unique()), so lookups resolve to real
# road segments with real incident history instead of a generic fallback.
CORRIDOR_ALTERNATES = {
    'Tumkur Road':              ['Bellary Road 1', 'ORR North 1'],
    'Bellary Road 1':           ['Tumkur Road', 'ORR North 1'],
    'Bellary Road 2':           ['ORR North 2', 'Tumkur Road'],
    'Mysore Road':              ['Bannerghata Road', 'Magadi Road'],
    'Bannerghata Road':         ['Mysore Road', 'Hosur Road'],
    'Magadi Road':              ['Mysore Road', 'ORR West 1'],
    'Hosur Road':               ['ORR East 1', 'Bannerghata Road'],
    'Old Madras Road':          ['ORR East 1', 'Hennur Main Road'],
    'Hennur Main Road':         ['ORR North 2', 'Old Madras Road'],
    'IRR(Thanisandra road)':    ['ORR North 1', 'Hennur Main Road'],
    'Varthur Road':             ['ORR East 2', 'Old Madras Road'],
    'Old Airport Road':         ['ORR East 1', 'Varthur Road'],
    'Airport New South Road':  ['Old Airport Road', 'Hennur Main Road'],
    'West of Chord Road':       ['Magadi Road', 'CBD 1'],
    'CBD 1':                    ['CBD 2', 'West of Chord Road'],
    'CBD 2':                    ['CBD 1', 'Hosur Road'],
    'ORR North 1':              ['Bellary Road 1', 'Tumkur Road'],
    'ORR North 2':              ['Bellary Road 2', 'Hennur Main Road'],
    'ORR East 1':               ['Hosur Road', 'Old Madras Road'],
    'ORR East 2':               ['Varthur Road', 'Old Madras Road'],
    'ORR West 1':               ['Mysore Road', 'Magadi Road'],
}


def get_corridor_alternates(corridor):
    if not corridor:
        return []
    corridor_lower = str(corridor).lower()
    for key, alts in CORRIDOR_ALTERNATES.items():
        if key.lower() in corridor_lower or corridor_lower in key.lower():
            return alts
    # Generic fallback
    return ['ORR North 1', 'Hosur Road']


def _corridor_matches(df, corridor_name):
    if not corridor_name or 'corridor' not in df.columns:
        return df.iloc[0:0]
    corridor_lower = str(corridor_name).lower()
    known = df[df['corridor'].notna()]
    mask = known['corridor'].str.lower().apply(
        lambda c: c in corridor_lower or corridor_lower in c
    )
    return known[mask]


def get_corridor_centroid(df, corridor_name):
    """Mean lat/lon of a named corridor's historical incidents, or None."""
    matches = _corridor_matches(df, corridor_name)
    if matches.empty:
        return None
    return (matches['latitude'].mean(), matches['longitude'].mean())


def get_corridor_far_point(df, corridor_name, from_lat, from_lon):
    """The corridor incident point farthest from (from_lat, from_lon) --
    a 'continue down this corridor past the jam' destination, instead of
    the centroid (which can sit right next to the incident itself)."""
    matches = _corridor_matches(df, corridor_name)
    if matches.empty:
        return None
    dist2 = (matches['latitude'] - from_lat) ** 2 + (matches['longitude'] - from_lon) ** 2
    far = matches.loc[dist2.idxmax()]
    return (far['latitude'], far['longitude'])


def make_route_map(df, incident_lat, incident_lon, corridor_name, alt_corridor_name):
    """Folium map showing two ways to reach the SAME destination (a point
    further down the congested corridor): red is the direct route (which
    runs through the jam), green is a route forced via the alternate
    corridor. Uses real Mappls road routing when available, falls back to
    a straight dashed line if the API call fails."""
    import folium
    from src import mappls_rest

    origin = (incident_lat, incident_lon)
    dest = get_corridor_far_point(df, corridor_name, incident_lat, incident_lon)
    alt_via = get_corridor_centroid(df, alt_corridor_name)

    m = folium.Map(location=list(origin), zoom_start=12, tiles='CartoDB positron')

    folium.Marker(
        location=list(origin),
        icon=folium.Icon(color='red', icon='exclamation-sign'),
        tooltip='Incident location',
    ).add_to(m)

    all_points = [origin]

    def _draw(waypoint, color, label):
        if not dest:
            return
        route = mappls_rest.get_route(origin, dest, waypoint=waypoint)
        if route:
            folium.PolyLine(route, color=color, weight=5, opacity=0.8, tooltip=label).add_to(m)
            all_points.extend(route)
        else:
            points = [origin] + ([waypoint] if waypoint else []) + [dest]
            folium.PolyLine(
                points, color=color, weight=4, opacity=0.6,
                dash_array='8', tooltip=f"{label} (approximate)",
            ).add_to(m)
            all_points.extend(points)

    _draw(None, '#c0392b', f"Direct, via congested corridor: {corridor_name}")
    _draw(alt_via, '#27ae60', f"Diverted via alternate: {alt_corridor_name}")

    # zoom_start=12 above is just an initial value -- fit_bounds overrides it
    # so the shared destination (which can be many km from the incident) is
    # always in view instead of getting cropped off the edge of the map.
    if len(all_points) > 1:
        lats = [p[0] for p in all_points]
        lons = [p[1] for p in all_points]
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                padding:10px 14px;border-radius:6px;border:1px solid #ccc;font-size:13px;">
        <span style="color:#c0392b;">&#9473;&#9473;</span> Direct (via congested corridor)<br>
        <span style="color:#27ae60;">&#9473;&#9473;</span> Diverted (via alternate)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    return m
