"""
Incident clearance timer — expected clearance time for an active report,
based on the historical median duration for that cause.
"""
from datetime import datetime, timedelta

DEFAULT_CLEARANCE_MINS = 30


def expected_clearance_mins(df, cause):
    if 'duration_mins' not in df.columns or 'event_cause' not in df.columns:
        return DEFAULT_CLEARANCE_MINS
    durations = df[df['event_cause'] == cause]['duration_mins'].dropna()
    if durations.empty:
        return DEFAULT_CLEARANCE_MINS
    return round(float(durations.median()))


def clearance_status(submitted_at, expected_mins):
    if submitted_at is None:
        return None
    elapsed = (datetime.now() - submitted_at).total_seconds() / 60
    clear_by = submitted_at + timedelta(minutes=expected_mins)
    return {
        'elapsed_mins': round(elapsed),
        'clear_by': clear_by,
        'overdue': elapsed > expected_mins,
    }
