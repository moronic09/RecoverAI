"""Unit tests for ML predictions."""

import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).parent
sys.path.insert(0, str(ML_DIR))


@pytest.fixture(scope="module", autouse=True)
def ensure_models():
    models_dir = ML_DIR / "models"
    if not (models_dir / "failure_classifier.joblib").exists():
        from train import main as train_main

        train_main()


def test_predict_returns_expected_keys():
    from predict import predict_transaction

    tx = {
        "amount": 1500.0,
        "payment_method": "card",
        "created_at": "2025-08-15T14:30:00",
        "retry_count": 0,
        "customer_failure_history": 1,
        "bank_code": "HDFC",
        "status": "failed",
    }
    result = predict_transaction(tx)

    assert "predicted_failure_class" in result
    assert "recovery_probability" in result
    assert "recommended_action" in result
    assert 0 <= result["recovery_probability"] <= 1
    assert 0 <= result["failure_confidence"] <= 1


def test_high_recovery_for_network_error_pattern():
    from predict import predict_transaction

    tx = {
        "amount": 500.0,
        "payment_method": "upi",
        "created_at": "2025-08-15T10:00:00",
        "retry_count": 0,
        "customer_failure_history": 0,
        "bank_code": None,
        "status": "failed",
        "failure_reason": "network_error",
    }
    result = predict_transaction(tx)
    assert result["recommended_action"] in (
        "auto_retry_immediate",
        "auto_retry_scheduled",
        "send_nudge_sms",
        "send_nudge_whatsapp",
        "manual_review",
    )


def test_feature_importances_available():
    from predict import get_global_feature_importances

    imps = get_global_feature_importances()
    assert len(imps) > 0
