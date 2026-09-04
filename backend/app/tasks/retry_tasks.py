"""Async retry simulation and nudge delivery for local background tasks."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def _execute_retry(transaction_id: int, attempt_number: int) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.recovery_attempt import RecoveryAttempt
    from app.models.transaction import Transaction
    from app.services.ml_service import MLService
    from app.services.redis_events import publish_event

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transaction)
            .where(Transaction.id == transaction_id)
            .options(selectinload(Transaction.ml_predictions))
        )
        tx = result.scalar_one_or_none()
        if not tx or tx.status == "captured":
            return {"status": "skipped", "reason": "already captured or not found"}

        prediction = tx.ml_predictions[-1] if tx.ml_predictions else None
        recovery_prob = prediction.recovery_probability if prediction else 0.3

        # Simulate outcome based on recovery probability
        success = random.random() < recovery_prob

        attempt = RecoveryAttempt(
            transaction_id=tx.id,
            attempt_number=attempt_number,
            status="executed",
            channel="auto_retry",
            message=f"Auto-retry attempt #{attempt_number}",
            scheduled_at=datetime.now(timezone.utc),
            executed_at=datetime.now(timezone.utc),
        )

        if success:
            tx.status = "captured"
            tx.recovered_amount = tx.amount
            attempt.outcome = "recovered"
            attempt.status = "recovered"
            event_type = "recovery_success"
        else:
            tx.retry_count += 1
            attempt.outcome = "failed"
            attempt.status = "failed"
            event_type = "retry_failed"

        db.add(attempt)
        await db.commit()

        event = {
            "event_type": event_type,
            "transaction_id": tx.id,
            "data": {
                "amount": float(tx.amount),
                "status": tx.status,
                "attempt_number": attempt_number,
                "recovery_probability": recovery_prob,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        publish_event(event)
        return {"status": "success" if success else "failed", "transaction_id": tx.id}


async def _send_nudge(transaction_id: int, channel: str) -> dict:
    from app.database import AsyncSessionLocal
    from app.models.recovery_attempt import RecoveryAttempt
    from app.models.transaction import Transaction
    from app.services.redis_events import publish_event

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
        tx = result.scalar_one_or_none()
        if not tx:
            return {"status": "error", "reason": "not found"}

        channel = channel.removeprefix("nudge_")
        delivery_statuses = ["delivered", "delivered", "delivered", "failed", "pending"]
        status = random.choice(delivery_statuses)

        messages = {
            "sms": f"Payment of ₹{tx.amount} failed. Retry securely: https://pay.example.com/{tx.razorpay_payment_id}",
            "email": f"Subject: Action needed for your ₹{tx.amount} payment\n\nYour payment was unsuccessful. Please update your payment method and try again.",
            "whatsapp": f"Your ₹{tx.amount} payment did not go through. When convenient, please try again to complete your order.",
        }

        attempt = RecoveryAttempt(
            transaction_id=tx.id,
            attempt_number=tx.retry_count + 1,
            status=status,
            channel=channel,
            message=messages.get(channel, messages["sms"]),
            outcome=status,
            executed_at=datetime.now(timezone.utc),
        )
        db.add(attempt)
        await db.commit()

        event = {
            "event_type": "nudge_sent",
            "transaction_id": tx.id,
            "data": {"channel": channel, "status": status},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        publish_event(event)
        return {"status": status, "channel": channel}


async def process_retry(transaction_id: int, attempt_number: int = 1):
    return await _execute_retry(transaction_id, attempt_number)


async def send_nudge(transaction_id: int, channel: str = "sms"):
    return await _send_nudge(transaction_id, channel)


async def schedule_retry(transaction_id: int, delay_seconds: int = 30):
    await asyncio.sleep(delay_seconds)
    return await _execute_retry(transaction_id, 1)
