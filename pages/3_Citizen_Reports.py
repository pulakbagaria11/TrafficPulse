import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_prep import load_data, BENGALURU_CENTER, cause_label
from src.reporter_score import submit_report, get_all_reports, init_reports
from src.violation_hotspot import get_violation_hotspots
from src.incident_response import recommend_for_location
from src.clearance import expected_clearance_mins, clearance_status

st.set_page_config(page_title="Citizen Reports | TrafficPulse", layout="wide")
st.markdown("<style>h1,h2,h3{font-weight:600;}.stMetric label{font-size:0.8rem;color:#666;}</style>",
            unsafe_allow_html=True)

st.title("Citizen Reports")
init_reports()
df = load_data()

BENGALURU_AREAS = {
    'Majestic / City Centre': (12.9767, 77.5713),
    'Koramangala': (12.9352, 77.6245),
    'Indiranagar': (12.9784, 77.6408),
    'Whitefield': (12.9698, 77.7500),
    'Electronic City': (12.8458, 77.6601),
    'Hebbal': (13.0358, 77.5970),
    'Rajajinagar': (12.9915, 77.5521),
    'Marathahalli': (12.9591, 77.6972),
    'Yeshwanthpur': (13.0258, 77.5461),
    'Tumkur Road corridor': (13.0200, 77.5100),
    'Bannerghatta Road corridor': (12.8875, 77.5946),
    'Outer Ring Road': (12.9698, 77.7100),
    'Silk Board junction': (12.9177, 77.6237),
    'K R Puram': (13.0078, 77.6942),
}

# --- VIP Alert ---
if df is not None and 'event_cause' in df.columns:
    recent_vip = df[df['event_cause'] == 'vip_movement']
    if not recent_vip.empty:
        vip = recent_vip.sort_values('start_datetime', ascending=False).iloc[0]
        corridor = str(vip.get('corridor', 'City corridor')).strip()
        if corridor and corridor not in ('nan', ''):
            st.markdown(
                f"""<div style="background:#7f1d1d;color:white;padding:0.7rem 1rem;
                border-radius:5px;margin-bottom:1rem;font-size:0.9rem;">
                <b>Historical Example — VIP Movement</b> &nbsp;|&nbsp;
                Corridor: {corridor} &nbsp;|&nbsp; Road closure required.
                Plan alternate routes.
                </div>""",
                unsafe_allow_html=True,
            )

# --- Tabs ---
tab_citizen, tab_police = st.tabs(["Submit a Report", "Police View"])

# ===================== CITIZEN TAB =====================
with tab_citizen:
    st.caption("Report a traffic incident directly from the field. Verified by TrafficPulse when 3 or more reports arrive from the same area.")

    left, right = st.columns([1, 1])

    with left:
        # GPS detection
        if 'gps_active' not in st.session_state:
            st.session_state['gps_active'] = False
        if 'gps_area' not in st.session_state:
            st.session_state['gps_area'] = None

        gps_col, _ = st.columns([1, 2])
        with gps_col:
            if st.button("Detect My Location", use_container_width=True):
                st.session_state['gps_active'] = True
                st.session_state['gps_area'] = 'Majestic / City Centre'

        if st.session_state['gps_active']:
            st.success("Location detected. You can change it below if incorrect.")

        with st.form("report_form", clear_on_submit=True):
            reporter_id = st.text_input("Your name or ID (optional)")

            cause = st.selectbox(
                "What are you reporting?",
                options=[
                    'vehicle_breakdown', 'accident', 'pot_holes',
                    'water_logging', 'construction', 'tree_fall',
                    'procession', 'protest', 'congestion', 'other',
                ],
                format_func=lambda x: x.replace('_', ' ').title(),
            )
            if cause == 'pot_holes' and df is not None:
                pothole_count = int((df['event_cause'] == 'pot_holes').sum())
                recurring = get_violation_hotspots(df[df['event_cause'] == 'pot_holes'], min_incidents=2)
                st.caption(
                    f"{pothole_count} historical pothole incidents recorded citywide — "
                    f"{len(recurring)} recurring locations flagged."
                )

            default_area = st.session_state.get('gps_area') or 'Majestic / City Centre'
            area_options = list(BENGALURU_AREAS.keys())
            default_idx = area_options.index(default_area) if default_area in area_options else 0
            area = st.selectbox("Area / location", options=area_options, index=default_idx)

            desc = st.text_area("Describe the situation (optional)", max_chars=200,
                                placeholder="e.g. Lorry broken down blocking two lanes, traffic backing up 500m")

            submitted = st.form_submit_button("Submit Report", type="primary")

        if submitted:
            lat, lon = BENGALURU_AREAS[area]
            rid = reporter_id.strip() or f"ANON_{len(get_all_reports()) + 1}"
            idx = submit_report(rid, cause, lat, lon, desc)
            reports = get_all_reports()
            report = reports.iloc[idx]
            if report.get('verified'):
                st.success("Report submitted and auto-verified — 3 or more reports in this area confirmed the incident.")
            else:
                st.success("Report submitted. Pending verification.")
            st.session_state['gps_active'] = False

    with right:
        st.markdown("**How it works**")
        st.markdown("""
        1. Tap **Detect My Location** or select your area
        2. Choose the incident type and describe what you see
        3. Submit — your report is sent to the TrafficPulse control room
        4. When 3 or more reports arrive from the same area, the incident is **auto-verified** and officers are alerted
        5. Verified reports earn **10 points** on the Reporter Leaderboard
        """)

        # Preview map of selected area
        preview_area = list(BENGALURU_AREAS.keys())[0]
        coords = BENGALURU_AREAS.get(preview_area, BENGALURU_CENTER)
        pm = folium.Map(location=list(coords), zoom_start=13, tiles='CartoDB positron')
        folium.Marker(
            location=list(coords),
            icon=folium.Icon(color='red', icon='info-sign'),
            tooltip="Your selected area",
        ).add_to(pm)
        st.caption("Location preview")
        st_folium(pm, width=None, height=240, returned_objects=[])


# ===================== POLICE VIEW TAB =====================
with tab_police:
    reports_df = get_all_reports()

    if reports_df.empty:
        pending_ct = 0
        verified_ct = 0
    else:
        verified_ct = int(reports_df['verified'].sum())
        pending_ct = len(reports_df) - verified_ct

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Reports", len(reports_df) if not reports_df.empty else 0)
    c2.metric("Verified", verified_ct)
    c3.metric("Pending Verification", pending_ct)

    st.markdown("---")

    map_col, feed_col = st.columns([3, 2])

    with map_col:
        st.subheader("Report Map")
        pm = folium.Map(location=BENGALURU_CENTER, zoom_start=11, tiles='CartoDB positron')

        # Background: recent Astram events
        if df is not None:
            sample = df.head(100)
            for _, row in sample.iterrows():
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=3,
                    color='#aaa',
                    fill=True,
                    fill_opacity=0.3,
                    tooltip=f"Astram: {cause_label(str(row.get('event_cause', '')))}",
                ).add_to(pm)

        # Citizen reports
        if not reports_df.empty:
            for _, row in reports_df.iterrows():
                color = '#27ae60' if row.get('verified') else '#e67e22'
                popup_html = (
                    f"<b>{str(row['cause']).replace('_',' ').title()}</b><br>"
                    f"By: {row['reporter_id']}<br>"
                    f"Status: {'Verified' if row.get('verified') else 'Pending'}<br>"
                    f"{row.get('description','') or ''}"
                )
                if row['cause'] == 'pot_holes':
                    folium.Marker(
                        location=[row['lat'], row['lon']],
                        icon=folium.Icon(
                            color='green' if row.get('verified') else 'orange',
                            icon='wrench', prefix='glyphicon',
                        ),
                        popup=folium.Popup(popup_html, max_width=220),
                    ).add_to(pm)
                else:
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']],
                        radius=10,
                        color=color,
                        fill=True,
                        fill_opacity=0.85,
                        popup=folium.Popup(popup_html, max_width=220),
                    ).add_to(pm)

        st_folium(pm, width=None, height=420, returned_objects=[])
        st.caption("Gray: historical Astram events   Green: verified citizen reports   Orange: pending reports")

    with feed_col:
        st.subheader("Incoming Reports")

        if reports_df.empty:
            st.info("No reports submitted in this session.")
            st.caption("Reports submitted via the Submit tab appear here in real time.")
        else:
            for i, row in reports_df.iterrows():
                status_color = '#27ae60' if row.get('verified') else '#e67e22'
                status_text = 'Verified' if row.get('verified') else 'Pending'
                cause_text = str(row['cause']).replace('_', ' ').title()
                desc_text = row.get('description', '') or ''

                st.markdown(
                    f"""<div style="border-left:4px solid {status_color};
                    padding:0.5rem 0.8rem;margin-bottom:0.5rem;background:#f9f9f9;border-radius:3px;">
                    <b>{cause_text}</b> &nbsp;
                    <span style="background:{status_color};color:white;padding:1px 6px;
                    border-radius:3px;font-size:0.75rem;">{status_text}</span><br>
                    <span style="font-size:0.8rem;color:#555;">
                    {row['reporter_id']} &nbsp;|&nbsp; {row['lat']:.3f}, {row['lon']:.3f}
                    {(' — ' + desc_text[:60]) if desc_text else ''}
                    </span>
                    </div>""",
                    unsafe_allow_html=True,
                )

                if df is not None:
                    clear = clearance_status(row.get('submitted_at'), expected_clearance_mins(df, row['cause']))
                    rec = recommend_for_location(df, row['cause'], row['lat'], row['lon'])

                    info_bits = []
                    if clear:
                        timer_color = '#c0392b' if clear['overdue'] else '#555'
                        info_bits.append(
                            f"<span style='color:{timer_color};'>Reported {clear['elapsed_mins']}m ago — "
                            f"expected clear by {clear['clear_by'].strftime('%H:%M')}"
                            f"{' (overdue)' if clear['overdue'] else ''}</span>"
                        )
                    info_bits.append(
                        f"Recommended: {rec['personnel']} officer(s)"
                        + (f", {rec['barricades']} barricade(s)" if rec['barricades'] else "")
                    )
                    st.markdown(
                        f"<div style='font-size:0.78rem;color:#555;margin:-0.3rem 0 0.4rem 0;'>"
                        + " &nbsp;|&nbsp; ".join(info_bits) + "</div>",
                        unsafe_allow_html=True,
                    )
                    if rec.get('diversion') and rec.get('alternates'):
                        corridor_note = f" (corridor: {rec['corridor']})" if rec.get('corridor') else ""
                        st.markdown(
                            f"<div style='font-size:0.78rem;color:#1a3a5c;margin:-0.2rem 0 0.5rem 0;'>"
                            f"Diversion suggested via {rec['alternates'][0]}{corridor_note}</div>",
                            unsafe_allow_html=True,
                        )

                a_col, d_col = st.columns(2)
                with a_col:
                    if st.button("Acknowledge", key=f"ack_{i}", use_container_width=True):
                        st.toast(f"Report {i+1} acknowledged.")
                with d_col:
                    if st.button("Dispatch Officer", key=f"dis_{i}", use_container_width=True):
                        st.toast(f"Officer dispatched to report {i+1}.")


