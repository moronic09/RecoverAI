"""
ML inference module — load models once, predict on transaction features.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from features import FEATURE_COLUMNS, engineer_features

MODELS_DIR = Path(__file__).parent / "models"

_failure_model = None
_recovery_model = None
_label_encoder = None
_metadata: dict | None = None


def _load_models():
    global _failure_model, _recovery_model, _label_encoder, _metadata

    if _failure_model is not None:
        return

    failure_path = MODELS_DIR / "failure_classifier.joblib"
    recovery_path = MODELS_DIR / "recovery_model.joblib"
    encoder_path = MODELS_DIR / "failure_label_encoder.joblib"
    metadata_path = MODELS_DIR / "model_metadata.json"

    if not failure_path.exists():
        raise FileNotFoundError(
            f"ML models not found at {MODELS_DIR}. Run: python ml/train.py"
        )

    _failure_model = joblib.load(failure_path)
    _recovery_model = joblib.load(recovery_path)
    _label_encoder = joblib.load(encoder_path)

    if metadata_path.exists():
        with open(metadata_path) as f:
            _metadata = json.load(f)
    else:
        _metadata = {"feature_columns": FEATURE_COLUMNS}


def recommend_action(failure_class: str, recovery_prob: float, retry_count: int) -> str:
    if recovery_prob >= 0.6:
        if retry_count == 0:
            return "auto_retry_immediate"
        return "auto_retry_scheduled"
    if recovery_prob >= 0.35:
        return "send_nudge_sms"
    if recovery_prob >= 0.15:
        return "send_nudge_whatsapp"
    if failure_class in ("card_expired", "invalid_card"):
        return "request_updated_payment_method"
    return "manual_review"


def predict_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Run full ML inference on a single transaction dict."""
    _load_models()

    df = pd.DataFrame([transaction])
    features = engineer_features(df)

    # Failure classification
    fail_proba = _failure_model.predict_proba(features)[0]
    fail_idx = int(np.argmax(fail_proba))
    failure_class = _label_encoder.classes_[fail_idx]
    failure_confidence = float(fail_proba[fail_idx])

    # Recovery probability
    recovery_prob = float(_recovery_model.predict_proba(features)[0][1])

    retry_count = int(transaction.get("retry_count", 0))
    action = recommend_action(failure_class, recovery_prob, retry_count)

    # Per-prediction feature importances from global model metadata
    importances = {}
    if _metadata:
        src = _metadata.get("failure_feature_importances", {})
        for feat, imp in src.items():
            importances[feat] = round(imp * features[feat].iloc[0] if feat in features.columns else imp, 4)

    return {
        "predicted_failure_class": failure_class,
        "failure_confidence": round(failure_confidence, 4),
        "recovery_probability": round(recovery_prob, 4),
        "recommended_action": action,
        "feature_importances": _metadata.get("failure_feature_importances", {}) if _metadata else {},
        "feature_values": {col: float(features[col].iloc[0]) for col in FEATURE_COLUMNS},
    }


def get_global_feature_importances() -> dict[str, float]:
    _load_models()
    if _metadata:
        return _metadata.get("failure_feature_importances", {})
    return {}
