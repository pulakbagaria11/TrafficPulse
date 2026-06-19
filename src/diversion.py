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


def get_corridor_centroid(df, corridor_name):
    """Mean lat/lon of a named corridor's historical incidents, or None."""
    if not corridor_name or 'corridor' not in df.columns:
        return None
    corridor_lower = str(corridor_name).lower()
    known = df[df['corridor'].notna()]
    mask = known['corridor'].str.lower().apply(
        lambda c: c in corridor_lower or corridor_lower in c
    )
    matches = known[mask]
    if matches.empty:
        return None
    return (matches['latitude'].mean(), matches['longitude'].mean())


def make_route_map(df, incident_lat, incident_lon, corridor_name, alt_corridor_name):
    """Folium map: red route through the congested corridor, green route via
    the suggested alternate. Uses real Mappls road routing when available,
    falls back to a straight dashed line if the API call fails."""
    import folium
    from src.data_prep import BENGALURU_CENTER
    from src import mappls_rest

    origin = (incident_lat, incident_lon)
    congested_dest = get_corridor_centroid(df, corridor_name)
    alt_dest = get_corridor_centroid(df, alt_corridor_name)

    m = folium.Map(location=list(origin), zoom_start=12, tiles='CartoDB positron')

    folium.Marker(
        location=list(origin),
        icon=folium.Icon(color='red', icon='exclamation-sign'),
        tooltip='Incident location',
    ).add_to(m)

    def _draw(dest, color, label):
        if not dest:
            return
        route = mappls_rest.get_route(origin, dest)
        if route:
            folium.PolyLine(route, color=color, weight=5, opacity=0.8, tooltip=label).add_to(m)
        else:
            folium.PolyLine(
                [origin, dest], color=color, weight=4, opacity=0.6,
                dash_array='8', tooltip=f"{label} (approximate)",
            ).add_to(m)

    _draw(congested_dest, '#c0392b', f"Congested: {corridor_name}")
    _draw(alt_dest, '#27ae60', f"Alternate: {alt_corridor_name}")

    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                padding:10px 14px;border-radius:6px;border:1px solid #ccc;font-size:13px;">
        <span style="color:#c0392b;">&#9473;&#9473;</span> Congested corridor<br>
        <span style="color:#27ae60;">&#9473;&#9473;</span> Suggested alternate
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    return m
