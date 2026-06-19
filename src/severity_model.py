import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score
import lightgbm as lgb
import streamlit as st

CAT_COLS = ['event_cause', 'event_type']
NUM_COLS = ['hour', 'weekday', 'is_weekend', 'is_peak_hour', 'month', 'latitude', 'longitude']


@st.cache_resource
def train_models(df):
    feat_df = df.copy()
    encoders = {}

    for c in CAT_COLS:
        if c in feat_df.columns:
            le = LabelEncoder()
            feat_df[c + '_enc'] = le.fit_transform(
                feat_df[c].fillna('unknown').astype(str)
            )
            encoders[c] = le

    feature_cols = []
    for c in CAT_COLS:
        if c + '_enc' in feat_df.columns:
            feature_cols.append(c + '_enc')
    for c in NUM_COLS:
        if c in feat_df.columns:
            feature_cols.append(c)

    X = feat_df[feature_cols].fillna(-1)
    models = {}

    # Temporal split: train on Nov-Feb (months 11,12,1,2), test on Mar-Apr (3,4)
    if 'month' in feat_df.columns:
        train_mask = feat_df['month'].isin([11, 12, 1, 2])
        test_mask = feat_df['month'].isin([3, 4])
    else:
        from sklearn.model_selection import train_test_split
        idx = feat_df.index
        tr_idx, te_idx = train_test_split(idx, test_size=0.25, random_state=42)
        train_mask = feat_df.index.isin(tr_idx)
        test_mask = feat_df.index.isin(te_idx)

    lgb_params = dict(
        n_estimators=200,
        learning_rate=0.05,
        num_leaves=20,
        max_depth=5,
        min_child_samples=30,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        verbose=-1,
    )

    if 'priority_enc' in feat_df.columns:
        y = feat_df['priority_enc']
        valid_mask = y.notna()
        X_tr = X[train_mask & valid_mask]
        y_tr = y[train_mask & valid_mask]
        X_te = X[test_mask & valid_mask]
        y_te = y[test_mask & valid_mask]

        if len(X_tr) > 0 and len(X_te) > 0:
            m = lgb.LGBMClassifier(**lgb_params)
            m.fit(X_tr, y_tr)
            acc = accuracy_score(y_te, m.predict(X_te))
            models['priority'] = {
                'model': m,
                'accuracy': float(acc),
                'train_size': len(X_tr),
                'test_size': len(X_te),
                'feature_importance': dict(zip(feature_cols, m.feature_importances_)),
            }

    if 'closure_enc' in feat_df.columns:
        y = feat_df['closure_enc']
        valid_mask = y.notna()
        X_tr = X[train_mask & valid_mask]
        y_tr = y[train_mask & valid_mask]
        X_te = X[test_mask & valid_mask]
        y_te = y[test_mask & valid_mask]

        if len(X_tr) > 0 and len(X_te) > 0:
            pos_weight = len(y_tr[y_tr == 0]) / max(len(y_tr[y_tr == 1]), 1)
            m = lgb.LGBMClassifier(**lgb_params, scale_pos_weight=pos_weight)
            m.fit(X_tr, y_tr)
            acc = accuracy_score(y_te, m.predict(X_te))
            models['closure'] = {
                'model': m,
                'accuracy': float(acc),
                'train_size': len(X_tr),
                'test_size': len(X_te),
                'feature_importance': dict(zip(feature_cols, m.feature_importances_)),
            }

    return models, encoders, feature_cols


@st.cache_data(show_spinner=False)
def walk_forward_accuracy(df, initial_days=14, step_days=1):
    """Simulates a real learning loop: train on the first `initial_days`
    days, test on the next `step_days` day(s), then extend the training
    window and repeat through the whole dataset -- the model is retrained
    at every step instead of trained once and left fixed."""
    d = df.dropna(subset=['start_datetime', 'priority_enc']).copy()
    if d.empty:
        return pd.DataFrame()

    d['date'] = d['start_datetime'].dt.date
    encoders = {}
    for c in CAT_COLS:
        if c in d.columns:
            le = LabelEncoder()
            d[c + '_enc'] = le.fit_transform(d[c].fillna('unknown').astype(str))
            encoders[c] = le

    feature_cols = [c + '_enc' for c in CAT_COLS if c + '_enc' in d.columns]
    feature_cols += [c for c in NUM_COLS if c in d.columns]
    X = d[feature_cols].fillna(-1)
    y = d['priority_enc']

    start_date = d['date'].min()
    end_date = d['date'].max()
    cursor = start_date + pd.Timedelta(days=initial_days)
    step = pd.Timedelta(days=step_days)

    lgb_params = dict(
        n_estimators=100, learning_rate=0.08, num_leaves=15, max_depth=4,
        min_child_samples=15, reg_alpha=0.1, reg_lambda=0.1,
        random_state=42, verbose=-1,
    )

    results = []
    progress = st.progress(0.0, text="Simulating day-by-day retraining...")
    total_steps = max(1, int((end_date - cursor) / step) + 1)
    i = 0
    while cursor <= end_date:
        train_mask = d['date'] < cursor
        test_mask = (d['date'] >= cursor) & (d['date'] < cursor + step)
        X_tr, y_tr = X[train_mask], y[train_mask]
        X_te, y_te = X[test_mask], y[test_mask]

        if len(X_tr) >= 20 and len(X_te) > 0 and y_tr.nunique() > 1:
            m = lgb.LGBMClassifier(**lgb_params)
            m.fit(X_tr, y_tr)
            acc = accuracy_score(y_te, m.predict(X_te))
            results.append({
                'date': cursor, 'accuracy': acc,
                'train_size': len(X_tr), 'test_size': len(X_te),
            })

        cursor += step
        i += 1
        progress.progress(min(i / total_steps, 1.0), text="Simulating day-by-day retraining...")

    progress.empty()
    return pd.DataFrame(results)


def predict_event(models, encoders, feature_cols, event_cause, event_type,
                  lat, lon, hour, weekday, month=1):
    row = {
        'hour': hour,
        'weekday': weekday,
        'is_weekend': 1 if weekday >= 5 else 0,
        'is_peak_hour': 1 if (7 <= hour <= 10 or 17 <= hour <= 20) else 0,
        'month': month,
        'latitude': lat,
        'longitude': lon,
    }

    for c in CAT_COLS:
        val = event_cause if c == 'event_cause' else event_type
        if c in encoders:
            try:
                row[c + '_enc'] = int(encoders[c].transform([str(val)])[0])
            except ValueError:
                row[c + '_enc'] = -1

    X = pd.DataFrame([row])[feature_cols].fillna(-1)
    out = {}
    for name, info in models.items():
        prob = float(info['model'].predict_proba(X)[0][1])
        out[name] = round(prob, 3)
    return out
