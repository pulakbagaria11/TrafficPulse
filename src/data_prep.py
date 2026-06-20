import pandas as pd
import numpy as np
from pathlib import Path
import streamlit as st

DATA_PATH = Path(__file__).parent.parent / "data" / "events.csv"

CAUSE_NORMALIZE = {
    'vehicle breakdown': 'vehicle_breakdown',
    'vehiclebreakdown': 'vehicle_breakdown',
    'breakdown': 'vehicle_breakdown',
    'pothole': 'pot_holes',
    'pot hole': 'pot_holes',
    'potholes': 'pot_holes',
    'waterlogging': 'water_logging',
    'water logging': 'water_logging',
    'water-logging': 'water_logging',
    'tree fall': 'tree_fall',
    'tree fallen': 'tree_fall',
    'road accident': 'accident',
    'accidents': 'accident',
    'public event': 'public_event',
    'vip movement': 'vip_movement',
    'road construction': 'construction',
    'fog / low visibility': 'fog_visibility',
    'fog/low visibility': 'fog_visibility',
}

CAUSE_LABELS = {
    'vehicle_breakdown': 'Vehicle Breakdown',
    'pot_holes': 'Pothole',
    'construction': 'Construction',
    'water_logging': 'Water Logging',
    'accident': 'Accident',
    'tree_fall': 'Tree Fall',
    'public_event': 'Public Event',
    'procession': 'Procession',
    'vip_movement': 'VIP Movement',
    'others': 'Others',
    'road_conditions': 'Road Conditions',
    'congestion': 'Congestion',
    'protest': 'Protest',
    'debris': 'Debris',
    'fog_visibility': 'Fog / Low Visibility',
    'test_demo': 'Test / Demo',
    'unknown': 'Unknown',
}

BENGALURU_CENTER = [12.9716, 77.5946]


def _find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


@st.cache_data(show_spinner="Loading data...")
def load_data(path=None):
    p = Path(path) if path else DATA_PATH
    if not p.exists():
        return None

    df = pd.read_csv(p, low_memory=False, na_values=['NULL', 'null', 'None', ''])
    df.columns = [
        c.strip().lower().replace(' ', '_').replace('-', '_')
        for c in df.columns
    ]

    lat_col = _find_col(df, ['latitude', 'lat', 'y'])
    lon_col = _find_col(df, ['longitude', 'lon', 'long', 'lng', 'x'])
    if lat_col and lat_col != 'latitude':
        df = df.rename(columns={lat_col: 'latitude'})
    if lon_col and lon_col != 'longitude':
        df = df.rename(columns={lon_col: 'longitude'})

    # The Astram system stores IST timestamps but labels them +00 (common Indian govt system bug).
    # Stripping the offset and parsing as naive gives correct IST hours.
    for col in ['start_datetime', 'end_datetime', 'closed_datetime']:
        if col in df.columns:
            stripped = df[col].astype(str).str.replace(
                r'\+\d{2}(:\d{2})?$', '', regex=True
            ).str.replace(r'\s*UTC$', '', regex=True)
            df[col] = pd.to_datetime(stripped, errors='coerce')

    if 'event_cause' in df.columns:
        df = df[df['event_cause'].astype(str).str.lower() != 'test_demo']
        df['event_cause'] = (
            df['event_cause']
            .fillna('unknown')
            .str.strip()
            .str.lower()
            .str.replace(r'\s+', ' ', regex=True)
        )
        df['event_cause'] = df['event_cause'].replace(CAUSE_NORMALIZE)

    if 'event_type' in df.columns:
        df['event_type'] = (
            df['event_type']
            .fillna('unknown')
            .str.strip()
            .str.lower()
            .str.replace(' ', '_')
        )

    if 'corridor' in df.columns:
        # "Non-corridor" is the Astram system's own placeholder for "not on a
        # named corridor" (38% of all rows) -- treat it as missing so it
        # never gets picked as a real road by diversion/route-map features.
        NON_CORRIDOR = {'non-corridor', 'non corridor', 'na', 'n/a', 'none', ''}
        is_placeholder = df['corridor'].astype(str).str.strip().str.lower().isin(NON_CORRIDOR)
        df.loc[is_placeholder, 'corridor'] = None

    if 'start_datetime' in df.columns:
        dt = df['start_datetime']
        df['hour'] = dt.dt.hour
        df['weekday'] = dt.dt.dayofweek
        df['is_weekend'] = df['weekday'].isin([5, 6]).astype(int)
        df['is_peak_hour'] = df['hour'].apply(
            lambda h: 1 if (7 <= h <= 10 or 17 <= h <= 20) else 0
        )
        df['month'] = dt.dt.month
        df['date'] = dt.dt.date

    if 'closed_datetime' in df.columns and 'start_datetime' in df.columns:
        diff = (df['closed_datetime'] - df['start_datetime']).dt.total_seconds() / 60
        df['duration_mins'] = diff.clip(0, 720)

    if 'priority' in df.columns:
        df['priority_enc'] = (
            df['priority'].str.strip().str.lower() == 'high'
        ).astype(int)

    if 'requires_road_closure' in df.columns:
        col = df['requires_road_closure']
        if col.dtype == object:
            df['closure_enc'] = col.str.strip().str.lower().isin(
                ['true', 'yes', '1']
            ).astype(int)
        else:
            df['closure_enc'] = col.astype(bool).astype(int)

    for c in ['latitude', 'longitude']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    if 'latitude' in df.columns and 'longitude' in df.columns:
        df = df.dropna(subset=['latitude', 'longitude'])
        df = df[
            df['latitude'].between(12.7, 13.2) &
            df['longitude'].between(77.3, 77.8)
        ]

    df['lat_grid'] = df['latitude'].round(2)
    df['lon_grid'] = df['longitude'].round(2)

    return df.reset_index(drop=True)


def cause_label(cause):
    return CAUSE_LABELS.get(cause, cause.replace('_', ' ').title())
