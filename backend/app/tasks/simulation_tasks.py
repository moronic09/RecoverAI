"""Live transaction feed simulation for demo purposes."""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.services.redis_events import is_live_feed_enabled, publish_event


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _create_live_transaction(merchant_id: int = 1) -> dict | None:
    from app.database import AsyncSessionLocal
    from app.models.transaction import Transaction
    from app.services.ml_service import MLService

    PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
    FAILURE_REASONS = [
        "insufficient_funds", "network_error", "authentication_failed",
        "bank_declined", "timeout", "card_expired",
    ]
    BANK_CODES = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK"]

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.models.merchant import Merchant

        result = await db.execute(select(Merchant).where(Merchant.id == merchant_id))
        merchant = result.scalar_one_or_none()
        if not merchant:
            return None

        amount = round(random.uniform(99, 15000), 2)
        payment_method = random.choice(PAYMENT_METHODS)
        is_failed = random.random() < 0.75

        tx = Transaction(
            merchant_id=merchant_id,
            razorpay_payment_id=f"pay_{uuid.uuid4().hex[:16]}",
            razorpay_order_id=f"order_{uuid.uuid4().hex[:12]}",
            amount=Decimal(str(amount)),
            currency="INR",
            status="failed" if is_failed else "captured",
            payment_method=payment_method,
            failure_reason=random.choice(FAILURE_REASONS) if is_failed else None,
            failure_code="PAYMENT_DECLINED" if is_failed else None,
            customer_id=f"cust_{random.randint(1, 999):04d}",
            customer_email=f"live{random.randint(1000,9999)}@demo.com",
            customer_phone=f"+91{random.randint(7000000000, 9999999999)}",
            bank_code=random.choice(BANK_CODES) if payment_method in ("card", "netbanking") else None,
            retry_count=0,
            customer_failure_history=random.randint(0, 5),
        )
        db.add(tx)
        await db.flush()

        if is_failed:
            prediction = await MLService.predict_and_store(db, tx)
            pred_data = {
                "predicted_failure_class": prediction.predicted_failure_class,
                "recovery_probability": prediction.recovery_probability,
                "recommended_action": prediction.recommended_action,
            }
        else:
            pred_data = {}

        await db.commit()

        event = {
            "event_type": "new_transaction",
            "transaction_id": tx.id,
            "data": {
                "razorpay_payment_id": tx.razorpay_payment_id,
                "amount": float(tx.amount),
                "status": tx.status,
                "payment_method": tx.payment_method,
                "failure_reason": tx.failure_reason,
                **pred_data,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        publish_event(event)
        return event


async def generate_live_event():
    if not is_live_feed_enabled():
        return {"skipped": True, "reason": "live feed disabled"}
    return await _create_live_transaction()
