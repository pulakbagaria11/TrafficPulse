import json
import streamlit as st
# v3


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
    """
    Renders incident markers on a Mappls vector map with live traffic layer.
    Runs entirely client-side — no server-side API calls.
    The domain 'trafficpulse.streamlit.app' must be whitelisted in Mappls console.
    """
    key = _get_key()
    if not key:
        return None, "Mappls API key not configured in Streamlit secrets."

    safe = []
    for inc in incidents[:300]:
        lat = inc.get('lat', inc.get('latitude', 0))
        lon = inc.get('lon', inc.get('longitude', 0))
        if not lat or not lon:
            continue
        safe.append({
            'lat': round(float(lat), 5),
            'lon': round(float(lon), 5),
            'cause': str(inc.get('cause', inc.get('event_cause', ''))).replace('_', ' ').title(),
            'priority': str(inc.get('priority', '')),
            'color': '#c0392b' if str(inc.get('priority', '')).lower() == 'high' else '#1a3a5c',
        })

    incidents_json = json.dumps(safe)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ height:100%; overflow:hidden; }}
  #map {{ width:100%; height:{height}px; }}
  .legend {{
    position:absolute; bottom:24px; left:10px; z-index:999;
    background:rgba(255,255,255,0.92); padding:6px 10px;
    border-radius:4px; border:1px solid #ccc;
    font-family:sans-serif; font-size:11px; line-height:1.8;
  }}
  #debug {{
    position:absolute; top:0; left:0; right:0; z-index:1000;
    background:#fdecea; color:#611a15; font-family:monospace;
    font-size:11px; padding:4px 8px; display:none; white-space:pre-wrap;
  }}
</style>
</head>
<body>
<div id="debug"></div>
<div id="map"></div>
<div class="legend">
  <span style="color:#c0392b;">&#9679;</span> High Priority &nbsp;
  <span style="color:#1a3a5c;">&#9679;</span> Low Priority<br>
  <span style="color:#27ae60;">&#9679;</span> Citizen report (verified) &nbsp;
  <span style="color:#f39c12;">&#9679;</span> Pending
</div>
<script>
var INCIDENTS = {incidents_json};

function showDebug(msg) {{
  var d = document.getElementById('debug');
  d.style.display = 'block';
  d.innerText = msg;
}}
window.onerror = function(msg, url, line) {{
  showDebug('JS error: ' + msg + ' (line ' + line + ')');
}};

var sdkLoaded = false;

function initMap() {{
  sdkLoaded = true;
  try {{
    var map = new mappls.Map('map', {{
      center: [{center_lat}, {center_lon}],
      zoom: {zoom},
      geolocation: false,
      clickableIcons: false
    }});

    map.addListener('load', function() {{
      showDebug('Map loaded OK. ' + INCIDENTS.length + ' incidents to plot.');
      // Live traffic layer (best-effort — not all SDK builds expose this)
      try {{ new mappls.TrafficLayer({{ map: map }}); }} catch (e) {{}}

      // Place one marker per incident
      INCIDENTS.forEach(function(inc) {{
        new mappls.Marker({{
          map: map,
          position: {{ lat: inc.lat, lng: inc.lon }},
          fitbounds: false,
          icon: {{
            url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
              '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12">' +
              '<circle cx="6" cy="6" r="5" fill="' + inc.color + '" stroke="white" stroke-width="1"/>' +
              '</svg>'
            ),
            size: [12, 12]
          }},
          popupHtml: '<b>' + inc.cause + '</b><br>Priority: ' + inc.priority
        }});
      }});
    }});
  }} catch (e) {{
    showDebug('initMap failed: ' + e.message);
  }}
}}

setTimeout(function() {{
  if (!sdkLoaded) {{
    showDebug('Mappls SDK script never called initMap after 5s — script likely blocked (check domain whitelist / key / network tab for the sdk.mappls.com request).');
  }}
}}, 5000);
</script>
<script src="https://sdk.mappls.com/map/sdk/web?layer=vector&v=3.0&access_token={key}&callback=initMap" async defer
  onerror="showDebug('Failed to load Mappls SDK script (network/CORS/404 error).')"></script>
</body>
</html>"""

    return html, None


def make_route_map_html(origin_lat, origin_lon, dest_lat, dest_lon,
                        incident_lat=None, incident_lon=None,
                        incident_label="Incident", height=380):
    """
    Shows a Mappls map with a direction route drawn between origin and dest.
    The incident location is marked separately.
    All client-side — no server Python REST calls.
    """
    key = _get_key()
    if not key:
        return None, "Mappls API key not configured."

    inc_lat = incident_lat or (origin_lat + dest_lat) / 2
    inc_lon = incident_lon or (origin_lon + dest_lon) / 2

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ height:100%; overflow:hidden; }}
  #map {{ width:100%; height:{height}px; }}
  #route-info {{
    position:absolute; top:8px; right:8px; z-index:999;
    background:rgba(255,255,255,0.95); padding:8px 12px;
    border-radius:4px; border:1px solid #ccc;
    font-family:sans-serif; font-size:11px; min-width:160px;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div id="route-info">Calculating route...</div>
<script>
var ORIGIN = {{ lat: {origin_lat}, lng: {origin_lon} }};
var DEST   = {{ lat: {dest_lat},   lng: {dest_lon}   }};
var INC    = {{ lat: {inc_lat},    lng: {inc_lon}    }};
var INC_LABEL = "{incident_label}";

function initMap() {{
  var mid = [(ORIGIN.lat + DEST.lat)/2, (ORIGIN.lng + DEST.lng)/2];
  var map = new mappls.Map('map', {{
    center: mid,
    zoom: 12,
    geolocation: false
  }});

  map.addListener('load', function() {{
    try {{ new mappls.TrafficLayer({{ map: map }}); }} catch (e) {{}}

    // Mark the incident location
    new mappls.Marker({{
      map: map,
      position: INC,
      fitbounds: false,
      popupHtml: '<b>' + INC_LABEL + '</b><br>Incident location'
    }});

    // Draw the route using Mappls Direction
    try {{
      mappls.direction({{
        map: map,
        origin: ORIGIN,
        destination: DEST,
        alternatives: true,
        callback: function(data) {{
          if (data && data.routes && data.routes.length > 0) {{
            var r = data.routes[0];
            var legs = r.legs && r.legs[0];
            var dist = legs ? (legs.distance/1000).toFixed(1) + ' km' : '?';
            var time = legs ? Math.round(legs.duration/60) + ' min' : '?';
            document.getElementById('route-info').innerHTML =
              '<b>Alternate route</b><br>' +
              'Distance: ' + dist + '<br>' +
              'Est. time: ' + time;
          }} else {{
            document.getElementById('route-info').innerHTML = 'Route drawn on map';
          }}
        }}
      }});
    }} catch(e) {{
      // Fallback: show markers only
      new mappls.Marker({{ map: map, position: ORIGIN, fitbounds: false,
        popupHtml: '<b>Origin</b>' }});
      new mappls.Marker({{ map: map, position: DEST, fitbounds: false,
        popupHtml: '<b>Destination</b>' }});
      document.getElementById('route-info').innerHTML = 'Routing plugin loading...';
    }}
  }});
}}
</script>
<script src="https://sdk.mappls.com/map/sdk/web?layer=vector&v=3.0&plugins=direction&access_token={key}&callback=initMap" async defer></script>
</body>
</html>"""

    return html, None
