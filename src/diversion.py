"""
Diversion routing module.

Suggests alternate corridors using historical Astram corridor data —
no external routing API dependency.
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
