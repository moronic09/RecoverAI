"""
Generate realistic mock Razorpay-style transaction data for training and seeding.

Usage:
    python generate_mock_data.py --count 5000 --output data/transactions.csv
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

FAILURE_REASONS = {
    "insufficient_funds": {"weight": 0.28, "codes": ["BAD_REQUEST_ERROR", "PAYMENT_DECLINED"]},
    "card_expired": {"weight": 0.12, "codes": ["CARD_EXPIRED", "INVALID_EXPIRY"]},
    "network_error": {"weight": 0.15, "codes": ["GATEWAY_ERROR", "NETWORK_TIMEOUT"]},
    "authentication_failed": {"weight": 0.14, "codes": ["AUTHENTICATION_FAILED", "OTP_FAILED"]},
    "bank_declined": {"weight": 0.12, "codes": ["BANK_DECLINED", "ISSUER_UNAVAILABLE"]},
    "invalid_card": {"weight": 0.08, "codes": ["INVALID_CARD", "CARD_NOT_SUPPORTED"]},
    "timeout": {"weight": 0.06, "codes": ["PAYMENT_TIMEOUT", "SESSION_EXPIRED"]},
    "user_cancelled": {"weight": 0.05, "codes": ["USER_CANCELLED", "PAYMENT_CANCELLED"]},
}

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
PAYMENT_WEIGHTS = [0.45, 0.30, 0.15, 0.10]
BANK_CODES = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "PNB", "BOB", "YES", "IDFC", "OTHER"]

# Recovery probability by failure type (realistic priors)
RECOVERY_RATES = {
    "insufficient_funds": 0.35,
    "card_expired": 0.08,
    "network_error": 0.72,
    "authentication_failed": 0.55,
    "bank_declined": 0.25,
    "invalid_card": 0.05,
    "timeout": 0.65,
    "user_cancelled": 0.15,
}


def _weighted_choice(items: list, weights: list) -> str:
    return random.choices(items, weights=weights, k=1)[0]


def _generate_amount() -> float:
    """Log-normal amount distribution typical of Indian e-commerce."""
    base = np.random.lognormal(mean=6.5, sigma=1.2)
    return round(min(max(base, 49), 50000), 2)


def _time_of_day_bias(hour: int, failure_reason: str) -> None:
    """Night hours increase timeout/network errors slightly."""
    pass  # encoded via hour feature during training


def generate_transactions(count: int = 5000, days: int = 90, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    reasons = list(FAILURE_REASONS.keys())
    reason_weights = [FAILURE_REASONS[r]["weight"] for r in reasons]

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    customers: dict[str, int] = {}
    rows = []

    for i in range(count):
        customer_id = f"cust_{random.randint(1, 1200):05d}"
        customer_failures = customers.get(customer_id, 0)

        # ~70% failed, ~30% captured (some recovered)
        is_failed = random.random() < 0.70

        failure_reason = _weighted_choice(reasons, reason_weights)
        failure_info = FAILURE_REASONS[failure_reason]
        failure_code = random.choice(failure_info["codes"])

        payment_method = _weighted_choice(PAYMENT_METHODS, PAYMENT_WEIGHTS)
        amount = _generate_amount()
        bank_code = random.choice(BANK_CODES)

        # Time distribution: more activity 10am-10pm
        day_offset = random.randint(0, days - 1)
        hour = int(np.random.normal(16, 4)) % 24
        created_at = start_date + timedelta(days=day_offset, hours=hour, minutes=random.randint(0, 59))

        retry_count = random.randint(0, 3) if is_failed else random.randint(0, 2)

        if is_failed:
            status = "failed"
            recovered_amount = None
            customers[customer_id] = customer_failures + 1
        else:
            # Captured — possibly after retries
            status = "captured"
            recovered_amount = amount if random.random() < 0.6 else None
            if recovered_amount:
                failure_reason = random.choice(reasons)  # had a prior failure type

        rows.append(
            {
                "razorpay_payment_id": f"pay_{uuid.uuid4().hex[:16]}",
                "razorpay_order_id": f"order_{uuid.uuid4().hex[:12]}",
                "amount": amount,
                "currency": "INR",
                "status": status,
                "payment_method": payment_method,
                "failure_reason": failure_reason if status == "failed" else (
                    failure_reason if recovered_amount else None
                ),
                "failure_code": failure_code if status == "failed" else None,
                "customer_id": customer_id,
                "customer_email": f"user{customer_id.split('_')[1]}@example.com",
                "customer_phone": f"+91{random.randint(7000000000, 9999999999)}",
                "bank_code": bank_code if payment_method in ("card", "netbanking") else None,
                "retry_count": retry_count,
                "customer_failure_history": customer_failures,
                "recovered_amount": recovered_amount,
                "created_at": created_at.isoformat(),
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("created_at").reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Generate mock Razorpay transaction data")
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", type=str, default="data/transactions.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_path = Path(__file__).parent / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = generate_transactions(count=args.count, days=args.days, seed=args.seed)
    df.to_csv(output_path, index=False)

    failed = (df["status"] == "failed").sum()
    captured = (df["status"] == "captured").sum()
    print(f"Generated {len(df)} transactions -> {output_path}")
    print(f"  Failed: {failed} ({failed/len(df)*100:.1f}%)")
    print(f"  Captured: {captured} ({captured/len(df)*100:.1f}%)")
    print(f"  Date range: {df['created_at'].min()} to {df['created_at'].max()}")


if __name__ == "__main__":
    main()
