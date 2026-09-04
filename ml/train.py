"""
Train failure classification and recovery probability models.

Usage:
    python train.py
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from features import (
    FAILURE_CLASSES,
    FEATURE_COLUMNS,
    engineer_features,
    get_failure_label,
    get_recovery_label,
)

MODELS_DIR = Path(__file__).parent / "models"
DATA_PATH = Path(__file__).parent / "data" / "transactions.csv"


def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        from generate_mock_data import generate_transactions

        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        df = generate_transactions(count=5000)
        df.to_csv(DATA_PATH, index=False)
        print(f"Generated training data at {DATA_PATH}")
    return pd.read_csv(DATA_PATH)


def train_failure_classifier(X_train, y_train, X_test, y_test):
    le = LabelEncoder()
    le.fit(FAILURE_CLASSES)

    y_train_enc = le.transform(y_train)
    y_test_enc = le.transform(y_test)

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train_enc)

    y_pred = model.predict(X_test)
    print("\n=== Failure Classification Report ===")
    print(classification_report(y_test_enc, y_pred, target_names=le.classes_))

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist()))
    return model, le, importances


def train_recovery_model(X_train, y_train, X_test, y_test):
    model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_prob = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    print(f"\n=== Recovery Probability Model ===")
    print(f"ROC-AUC: {auc:.4f}")

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist()))
    return model, importances


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_data()
    failed_df = df[df["status"].isin(["failed", "captured"])].copy()

    # For failure classification, use failed transactions
    fail_df = df[df["status"] == "failed"].copy()
    if len(fail_df) < 100:
        fail_df = df.copy()

    features = engineer_features(fail_df)
    labels = get_failure_label(fail_df)

    X_train, X_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=42, stratify=labels
    )

    failure_model, label_encoder, fail_importances = train_failure_classifier(
        X_train, y_train, X_test, y_test
    )

    joblib.dump(failure_model, MODELS_DIR / "failure_classifier.joblib")
    joblib.dump(label_encoder, MODELS_DIR / "failure_label_encoder.joblib")

    # Recovery model: all transactions (failed + recovered)
    recovery_df = df.copy()
    rec_features = engineer_features(recovery_df)
    rec_labels = get_recovery_label(recovery_df)

    X_tr, X_te, y_tr, y_te = train_test_split(
        rec_features, rec_labels, test_size=0.2, random_state=42, stratify=rec_labels
    )

    recovery_model, rec_importances = train_recovery_model(X_tr, y_tr, X_te, y_te)

    joblib.dump(recovery_model, MODELS_DIR / "recovery_model.joblib")

    metadata = {
        "feature_columns": FEATURE_COLUMNS,
        "failure_classes": FAILURE_CLASSES,
        "failure_feature_importances": fail_importances,
        "recovery_feature_importances": rec_importances,
    }
    with open(MODELS_DIR / "model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nModels saved to {MODELS_DIR}")


if __name__ == "__main__":
    main()
