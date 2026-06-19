import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
import lightgbm as lgb
import streamlit as st

CAT_COLS = ['event_cause', 'event_type']
NUM_COLS = ['hour', 'weekday', 'is_weekend', 'is_peak_hour', 'month',
            'latitude', 'longitude']


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

    if 'priority_enc' in feat_df.columns:
        y = feat_df['priority_enc'].dropna()
        idx = y.index
        X_tr, X_te, y_tr, y_te = train_test_split(
            X.loc[idx], y, test_size=0.2, random_state=42
        )
        m = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05,
            num_leaves=31, random_state=42, verbose=-1
        )
        m.fit(X_tr, y_tr)
        models['priority'] = {
            'model': m,
            'accuracy': float((m.predict(X_te) == y_te).mean()),
            'feature_importance': dict(zip(feature_cols, m.feature_importances_)),
        }

    if 'closure_enc' in feat_df.columns:
        y = feat_df['closure_enc'].dropna()
        idx = y.index
        X_tr, X_te, y_tr, y_te = train_test_split(
            X.loc[idx], y, test_size=0.2, random_state=42
        )
        m = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.05,
            num_leaves=31, random_state=42, verbose=-1,
            scale_pos_weight=len(y_tr[y_tr == 0]) / max(len(y_tr[y_tr == 1]), 1)
        )
        m.fit(X_tr, y_tr)
        models['closure'] = {
            'model': m,
            'accuracy': float((m.predict(X_te) == y_te).mean()),
            'feature_importance': dict(zip(feature_cols, m.feature_importances_)),
        }

    return models, encoders, feature_cols


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
