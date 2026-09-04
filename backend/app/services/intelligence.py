"""Derived intelligence views built from existing ML predictions and transaction data."""

from datetime import datetime, timedelta, timezone
from collections import defaultdict
import math
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction

MERCHANT_TYPES = ("ecommerce", "subscription_saas", "edtech", "food_delivery")


def merchant_type_for(tx: Transaction) -> str:
    reason = tx.failure_reason or ""
    if reason in {"network_error", "timeout"} or tx.payment_method == "upi":
        return "food_delivery"
    if reason in {"card_expired", "insufficient_funds"}:
        return "subscription_saas"
    if tx.payment_method == "netbanking":
        return "edtech"
    return "ecommerce"


async def customer_failure_count_30d(db: AsyncSession, tx: Transaction) -> int:
    created_at = tx.created_at or datetime.now(timezone.utc)
    cutoff = created_at - timedelta(days=30)
    result = await db.execute(
        select(func.count()).where(
            Transaction.customer_id == tx.customer_id,
            Transaction.status == "failed",
            Transaction.created_at >= cutoff,
            Transaction.created_at <= created_at,
        )
    )
    return max(0, int(result.scalar() or 0) - (1 if tx.status == "failed" else 0))


def confidence_for(customer_failures: int, payment_method: str) -> str:
    if customer_failures >= 2:
        return "high"
    if customer_failures == 1 or payment_method in {"card", "upi"}:
        return "medium"
    return "low"


def adjust_probability(probability: float, customer_failures: int) -> float:
    multiplier = max(0.7, 1 - (0.08 * max(0, customer_failures - 1)))
    return round(max(0.0, min(1.0, probability * multiplier)), 4)


def failure_counts_30d(transactions: Iterable[Transaction]) -> dict[int, int]:
    items = list(transactions)
    counts: dict[int, int] = defaultdict(int)
    for tx in items:
        if tx.status != "failed":
            continue
        created_at = tx.created_at or datetime.now(timezone.utc)
        cutoff = created_at - timedelta(days=30)
        counts[tx.id] = sum(
            1 for other in items
            if other.customer_id == tx.customer_id
            and other.status == "failed"
            and cutoff <= (other.created_at or created_at) <= created_at
            and other.id != tx.id
        )
    return counts


def explain_prediction(prediction: Any, tx: Transaction, customer_failures: int) -> list[dict[str, str]]:
    values = {
        "amount_log": math.log(float(tx.amount) + 1),
        "retry_count": tx.retry_count,
        "customer_failure_history": tx.customer_failure_history,
        "payment_method_encoded": {"card": 0, "upi": 1, "netbanking": 2, "wallet": 3}.get(tx.payment_method, 0),
        "hour_of_day": (tx.created_at.hour if tx.created_at else 12),
    }
    importances = getattr(prediction, "feature_importances", None) or {}
    labels = {
        "retry_count": "Retry history",
        "customer_failure_history": "Customer history",
        "payment_method_encoded": f"Payment method: {tx.payment_method.title()}",
        "amount_log": "Payment amount",
        "hour_of_day": "Payment timing",
        "is_night": "Night-time payment",
    }
    candidates = []
    for feature, importance in importances.items():
        value = float(values.get(feature, 0))
        impact = abs(float(importance)) * (abs(value) + 0.25)
        if feature == "customer_failure_history" and customer_failures >= 2:
            direction, note = "-", f"{customer_failures} failures in 30 days indicate recovery fatigue"
        elif feature == "retry_count" and tx.retry_count > 0:
            direction, note = "-", "previous retries have not recovered this payment"
        elif feature == "amount_log":
            direction, note = "+", f"₹{float(tx.amount):,.2f} has meaningful recovery upside"
        elif feature == "payment_method_encoded":
            direction, note = "+", f"{tx.payment_method.title()} behavior contributes to the score"
        elif feature == "hour_of_day" and values[feature] >= 22:
            direction, note = "-", "late-night attempts are less likely to complete immediately"
        elif feature in {"is_night", "is_weekend"} and value:
            direction, note = "+", "timing can make a later retry more effective"
        else:
            direction, note = "+", "this feature contributes positively to the model score"
        candidates.append((impact, {"factor_name": labels.get(feature, feature.replace("_", " ").title()), "direction": direction, "impact_description": note}))
    return [item for _, item in sorted(candidates, key=lambda pair: pair[0], reverse=True)[:3]]