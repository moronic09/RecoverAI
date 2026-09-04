"""Feature engineering for RecoverAI ML models."""

from __future__ import annotations

import pandas as pd

FAILURE_CLASSES = [
    "insufficient_funds",
    "card_expired",
    "network_error",
    "authentication_failed",
    "bank_declined",
    "invalid_card",
    "timeout",
    "user_cancelled",
]

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
BANK_CODES = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "PNB", "BOB", "YES", "IDFC", "OTHER"]

FEATURE_COLUMNS = [
    "amount_log",
    "payment_method_encoded",
    "hour_of_day",
    "day_of_week",
    "retry_count",
    "customer_failure_history",
    "bank_code_encoded",
    "is_weekend",
    "is_night",
    "amount_bucket",
]


def encode_payment_method(method: str) -> int:
    mapping = {"card": 0, "upi": 1, "netbanking": 2, "wallet": 3}
    return mapping.get(method, 0)


def encode_bank_code(code: str | None) -> int:
    if not code:
        return len(BANK_CODES) - 1
    try:
        return BANK_CODES.index(code)
    except ValueError:
        return len(BANK_CODES) - 1


def amount_bucket(amount: float) -> int:
    if amount < 500:
        return 0
    if amount < 2000:
        return 1
    if amount < 10000:
        return 2
    return 3


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw transaction DataFrame into ML feature matrix."""
    out = df.copy()
    out["amount_log"] = (out["amount"].astype(float) + 1).apply(lambda x: __import__("math").log(x))
    out["payment_method_encoded"] = out["payment_method"].apply(encode_payment_method)
    out["hour_of_day"] = pd.to_datetime(out["created_at"]).dt.hour
    out["day_of_week"] = pd.to_datetime(out["created_at"]).dt.dayofweek
    out["bank_code_encoded"] = out["bank_code"].apply(encode_bank_code)
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)
    out["is_night"] = ((out["hour_of_day"] >= 22) | (out["hour_of_day"] <= 6)).astype(int)
    out["amount_bucket"] = out["amount"].astype(float).apply(amount_bucket)
    return out[FEATURE_COLUMNS]


def get_failure_label(df: pd.DataFrame) -> pd.Series:
    return df["failure_reason"].fillna("network_error")


def get_recovery_label(df: pd.DataFrame) -> pd.Series:
    """Binary: 1 if transaction was eventually recovered (captured after failure)."""
    return (df["status"] == "captured").astype(int)
