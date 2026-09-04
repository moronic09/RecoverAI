from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_merchant
from app.database import get_db
from app.models.merchant import Merchant
from app.models.ml_prediction import MLPrediction
from app.models.recovery_attempt import RecoveryAttempt
from app.models.transaction import Transaction
from app.schemas import (
    MLPredictionResponse,
    PredictResponse,
    RecoveryAttemptResponse,
    RetryResponse,
    TransactionResponse,
)
from app.services.ml_service import MLService
from app.services.recovery_decision import decision_for
from app.services.intelligence import adjust_probability, confidence_for, customer_failure_count_30d, explain_prediction
from app.tasks.retry_tasks import process_retry, schedule_retry, send_nudge
import uuid

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def _tx_to_response(tx: Transaction, db: AsyncSession) -> TransactionResponse:
    latest = tx.ml_predictions[-1] if tx.ml_predictions else None
    failure_count = await customer_failure_count_30d(db, tx) if latest else 0
    probability = adjust_probability(latest.recovery_probability, failure_count) if latest else None
    decision = decision_for(tx.amount, probability or 0, tx.failure_reason) if latest else {}
    confidence = confidence_for(failure_count, tx.payment_method) if latest else None
    return TransactionResponse(
        id=tx.id,
        razorpay_payment_id=tx.razorpay_payment_id,
        amount=tx.amount,
        currency=tx.currency,
        status=tx.status,
        payment_method=tx.payment_method,
        failure_reason=tx.failure_reason,
        failure_code=tx.failure_code,
        customer_id=tx.customer_id,
        customer_email=tx.customer_email,
        retry_count=tx.retry_count,
        customer_failure_history=tx.customer_failure_history,
        recovered_amount=tx.recovered_amount,
        created_at=tx.created_at,
        latest_prediction=MLPredictionResponse.model_validate(latest) if latest else None,
        **decision,
        customer_failure_count_30d=failure_count,
        fatigue_adjusted_probability=probability,
        confidence=confidence,
        explainability=explain_prediction(latest, tx, failure_count) if latest else [],
    )


@router.get("", response_model=list[TransactionResponse])
async def list_transactions(
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
):
    query = (
        select(Transaction)
        .where(Transaction.merchant_id == merchant.id)
        .options(selectinload(Transaction.ml_predictions))
    )

    if status_filter:
        query = query.where(Transaction.status == status_filter)

    if search:
        query = query.where(
            or_(
                Transaction.razorpay_payment_id.ilike(f"%{search}%"),
                Transaction.customer_id.ilike(f"%{search}%"),
                Transaction.customer_email.ilike(f"%{search}%"),
            )
        )

    sort_col = getattr(Transaction, sort_by, Transaction.created_at)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()
    return [await _tx_to_response(tx, db) for tx in transactions]


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.merchant_id == merchant.id)
        .options(selectinload(Transaction.ml_predictions))
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return await _tx_to_response(tx, db)


@router.get("/{transaction_id}/attempts", response_model=list[RecoveryAttemptResponse])
async def get_recovery_attempts(
    transaction_id: int,
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.merchant_id == merchant.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Transaction not found")

    attempts_result = await db.execute(
        select(RecoveryAttempt)
        .where(RecoveryAttempt.transaction_id == transaction_id)
        .order_by(RecoveryAttempt.created_at.desc())
    )
    return attempts_result.scalars().all()


@router.post("/{transaction_id}/predict", response_model=PredictResponse)
async def predict_transaction(
    transaction_id: int,
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.merchant_id == merchant.id)
        .options(selectinload(Transaction.ml_predictions))
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    prediction = await MLService.predict_and_store(db, tx)
    await db.commit()

    pred_result = MLService.predict(tx)
    failure_count = await customer_failure_count_30d(db, tx)
    adjusted_probability = adjust_probability(pred_result["recovery_probability"], failure_count)
    decision = decision_for(tx.amount, adjusted_probability, tx.failure_reason)
    return PredictResponse(
        transaction_id=tx.id,
        predicted_failure_class=pred_result["predicted_failure_class"],
        failure_confidence=pred_result["failure_confidence"],
        recovery_probability=adjusted_probability,
        recommended_action=pred_result["recommended_action"],
        feature_importances=pred_result.get("feature_importances", {}),
        feature_values=pred_result.get("feature_values", {}),
        recommended_channel=str(decision["recommended_channel"]),
        confidence=confidence_for(failure_count, tx.payment_method),
        explainability=explain_prediction(prediction, tx, failure_count),
        customer_failure_count_30d=failure_count,
    )


@router.post("/{transaction_id}/retry", response_model=RetryResponse)
async def retry_transaction(
    transaction_id: int,
    background_tasks: BackgroundTasks,
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction_id, Transaction.merchant_id == merchant.id)
        .options(selectinload(Transaction.ml_predictions))
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx.status == "captured":
        raise HTTPException(status_code=400, detail="Transaction already captured")

    attempt_number = tx.retry_count + 1
    task_id = str(uuid.uuid4())
    background_tasks.add_task(process_retry, transaction_id, attempt_number)

    return RetryResponse(
        transaction_id=transaction_id,
        task_id=task_id,
        message=f"Retry attempt #{attempt_number} queued",
        scheduled_at=datetime.now(timezone.utc),
    )
