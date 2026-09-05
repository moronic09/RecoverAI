"""
Seed database with curated demo data for impressive demos.

Usage:
    python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).parent.parent
ML_DIR = BACKEND_DIR.parent / "ml"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ML_DIR))

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.database import AsyncSessionLocal, engine, Base
from app.models.merchant import Merchant
from app.models.transaction import Transaction
from app.services.ml_service import MLService


async def seed(transaction_limit: int = 800):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Create demo merchant
        result = await db.execute(select(Merchant).where(Merchant.email == "demo@recoverai.com"))
        merchant = result.scalar_one_or_none()

        if not merchant:
            merchant = Merchant(
                email="demo@recoverai.com",
                password_hash=hash_password("demo1234"),
                name="Demo Merchant Pvt Ltd",
                razorpay_key_id="rzp_test_demo1234",
            )
            db.add(merchant)
            await db.flush()
            print(f"Created demo merchant (id={merchant.id})")
        else:
            print(f"Demo merchant exists (id={merchant.id})")

        # Check if transactions already seeded
        tx_count = await db.execute(
            select(Transaction).where(Transaction.merchant_id == merchant.id)
        )
        existing = tx_count.scalars().first()
        if existing:
            print("Transactions already seeded, skipping...")
            await db.commit()
            return

        # Load mock data
        csv_path = ML_DIR / "data" / "transactions.csv"
        if not csv_path.exists():
            from generate_mock_data import generate_transactions
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            df = generate_transactions(count=transaction_limit, seed=42)
            df.to_csv(csv_path, index=False)
            print(f"Generated {len(df)} transactions to {csv_path}")
        else:
            df = pd.read_csv(csv_path)
            print(f"Loaded {len(df)} transactions from {csv_path}")

        # Seed curated subset with good demo stats
        demo_df = df.head(transaction_limit).copy()
        print(f"Seeding {len(demo_df)} transactions...")

        batch_size = 100
        for i in range(0, len(demo_df), batch_size):
            batch = demo_df.iloc[i : i + batch_size]
            for _, row in batch.iterrows():
                created_at = datetime.fromisoformat(row["created_at"]).replace(tzinfo=timezone.utc)
                tx = Transaction(
                    merchant_id=merchant.id,
                    razorpay_payment_id=row["razorpay_payment_id"],
                    razorpay_order_id=row.get("razorpay_order_id"),
                    amount=Decimal(str(row["amount"])),
                    currency=row.get("currency", "INR"),
                    status=row["status"],
                    payment_method=row["payment_method"],
                    failure_reason=row.get("failure_reason") if pd.notna(row.get("failure_reason")) else None,
                    failure_code=row.get("failure_code") if pd.notna(row.get("failure_code")) else None,
                    customer_id=row["customer_id"],
                    customer_email=row.get("customer_email"),
                    customer_phone=row.get("customer_phone") if pd.notna(row.get("customer_phone")) else None,
                    bank_code=row.get("bank_code") if pd.notna(row.get("bank_code")) else None,
                    retry_count=int(row.get("retry_count", 0)),
                    customer_failure_history=int(row.get("customer_failure_history", 0)),
                    recovered_amount=Decimal(str(row["recovered_amount"])) if pd.notna(row.get("recovered_amount")) else None,
                    created_at=created_at,
                )
                db.add(tx)

            await db.flush()

            # Run ML predictions on failed transactions in batch
            failed_txs = await db.execute(
                select(Transaction).where(
                    Transaction.merchant_id == merchant.id,
                    Transaction.status == "failed",
                ).order_by(Transaction.id.desc()).limit(batch_size)
            )
            for tx in failed_txs.scalars().all():
                try:
                    await MLService.predict_and_store(db, tx)
                except Exception as e:
                    print(f"  ML prediction skipped for tx {tx.id}: {e}")

            await db.commit()
            print(f"  Seeded batch {i // batch_size + 1}/{(len(demo_df) + batch_size - 1) // batch_size}")

        print("\nDemo seed complete!")
        print("  Login: demo@recoverai.com / demo1234")


if __name__ == "__main__":
    asyncio.run(seed())
