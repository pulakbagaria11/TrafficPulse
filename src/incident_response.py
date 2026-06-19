"""
Barricade/diversion recommendations for real incoming incidents
(citizen reports), reusing the same tier logic the Prediction tool
uses for hypothetical events.
"""
from src.recommender import get_recommendation, calibrate_tiers
from src.diversion import get_corridor_alternates


def _nearest_corridor(df, lat, lon, radius_deg=0.02):
    if 'corridor' not in df.columns:
        return None
    nearby = df[
        df['corridor'].notna() &
        (df['latitude'] - lat).abs().lt(radius_deg) &
        (df['longitude'] - lon).abs().lt(radius_deg)
    ]
    if nearby.empty:
        return None
    top = nearby['corridor'].value_counts().index[0]
    return None if top.strip().lower() in ('non-corridor', 'non corridor') else top


def recommend_for_location(df, cause, lat, lon):
    rates = calibrate_tiers(df).get(cause, {})
    priority_prob = rates.get('high_priority_rate', 0.4)
    closure_prob = rates.get('closure_rate', 0.1)

    rec = get_recommendation(priority_prob, closure_prob, cause)
    corridor = _nearest_corridor(df, lat, lon)
    alts = get_corridor_alternates(corridor) if (corridor and rec.get('diversion')) else []

    return {
        'tier': rec['tier'],
        'personnel': rec['personnel'],
        'barricades': rec['barricades'],
        'diversion': rec['diversion'],
        'corridor': corridor,
        'alternates': alts,
    }
