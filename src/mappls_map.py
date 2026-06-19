import json
import streamlit as st


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


def make_incident_map_html(incidents, center_lat=12.9716, center_lon=77.5946,
                           zoom=11, height=500):
    key = _get_key()
    if not key:
        return None, "Mappls API key not configured."

    safe = []
    for inc in incidents[:300]:
        safe.append({
            'lat': float(inc.get('lat', inc.get('latitude', 0))),
            'lon': float(inc.get('lon', inc.get('longitude', 0))),
            'cause': str(inc.get('cause', inc.get('event_cause', ''))).replace('_', ' ').title(),
            'priority': str(inc.get('priority', '')),
            'color': '#c0392b' if str(inc.get('priority', '')).lower() == 'high' else '#2980b9',
        })

    incidents_json = json.dumps(safe)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ height:100%; }}
  #map {{ width:100%; height:{height}px; }}
  .info-panel {{
    position:absolute; bottom:30px; left:10px; background:white;
    padding:8px 12px; border-radius:4px; font-size:12px;
    border:1px solid #ccc; z-index:999; font-family:sans-serif;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div class="info-panel">
  <span style="color:#c0392b;">&#9679;</span> High Priority &nbsp;
  <span style="color:#2980b9;">&#9679;</span> Low Priority &nbsp;
  <span style="color:#f39c12;">&#9679;</span> Traffic (live)
</div>
<script>
var INCIDENTS = {incidents_json};

function initMap() {{
  var map = new mappls.Map('map', {{
    center: [{center_lat}, {center_lon}],
    zoom: {zoom},
    geolocation: false,
    clickableIcons: false
  }});

  map.addListener('load', function() {{
    // Traffic layer
    new mappls.TrafficLayer({{ map: map }});

    // Incident markers
    INCIDENTS.forEach(function(inc) {{
      if (!inc.lat || !inc.lon) return;
      var el = document.createElement('div');
      el.style.cssText = [
        'width:10px', 'height:10px', 'border-radius:50%',
        'background:' + inc.color,
        'border:1px solid white',
        'cursor:pointer'
      ].join(';');

      var marker = new mappls.Marker({{
        map: map,
        position: {{ lat: inc.lat, lng: inc.lon }},
        fitbounds: false,
        popupHtml: '<b>' + inc.cause + '</b><br>Priority: ' + inc.priority
      }});
    }});
  }});
}}
</script>
<script src="https://apis.mappls.com/advancedmaps/api/{key}/map_sdk?layer=vector&v=3.0&callback=initMap" async defer></script>
</body>
</html>"""

    return html, None


def make_route_map_html(origin_lat, origin_lon, dest_lat, dest_lon,
                        waypoints=None, height=400):
    key = _get_key()
    if not key:
        return None, "Mappls API key not configured."

    wp_json = json.dumps(waypoints or [])

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; }}
  #map {{ width:100%; height:{height}px; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
var ORIGIN = [{origin_lat}, {origin_lon}];
var DEST = [{dest_lat}, {dest_lon}];

function initMap() {{
  var midLat = (ORIGIN[0] + DEST[0]) / 2;
  var midLon = (ORIGIN[1] + DEST[1]) / 2;

  var map = new mappls.Map('map', {{
    center: [midLat, midLon],
    zoom: 12,
    geolocation: false
  }});

  map.addListener('load', function() {{
    new mappls.TrafficLayer({{ map: map }});

    new mappls.Marker({{
      map: map,
      position: {{ lat: ORIGIN[0], lng: ORIGIN[1] }},
      fitbounds: false,
      popupHtml: '<b>Origin</b>'
    }});

    new mappls.Marker({{
      map: map,
      position: {{ lat: DEST[0], lng: DEST[1] }},
      fitbounds: false,
      popupHtml: '<b>Destination</b>'
    }});

    mappls.direction({{
      map: map,
      origin: {{ lat: ORIGIN[0], lng: ORIGIN[1] }},
      destination: {{ lat: DEST[0], lng: DEST[1] }},
      alternatives: true,
      profile: 'driving'
    }});
  }});
}}
</script>
<script src="https://apis.mappls.com/advancedmaps/api/{key}/map_sdk?layer=vector&v=3.0&callback=initMap" async defer></script>
</body>
</html>"""

    return html, None
