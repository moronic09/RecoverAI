from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_merchant
from app.database import get_db
from app.models.merchant import Merchant
from app.models.ml_prediction import MLPrediction
from app.models.transaction import Transaction
from app.schemas import ABValidation, DashboardSummary, FailureBreakdownItem, StrategyComparison, TrendPoint
from app.services.ml_service import MLService
from app.services.recovery_decision import RETRY_COST, decision_for
from app.services.intelligence import MERCHANT_TYPES, adjust_probability, customer_failure_count_30d, failure_counts_30d, merchant_type_for

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_summary(
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
    merchant_type: str | None = None,
):
    if merchant_type in MERCHANT_TYPES:
        result = await db.execute(
            select(Transaction).where(Transaction.merchant_id == merchant.id).options(selectinload(Transaction.ml_predictions))
        )
        transactions = [tx for tx in result.scalars().all() if merchant_type_for(tx) == merchant_type]
        failed = [tx for tx in transactions if tx.status == "failed"]
        recovered = [tx for tx in transactions if tx.recovered_amount is not None]
        probabilities = [p.recovery_probability for tx in transactions for p in tx.ml_predictions[-1:]]
        return DashboardSummary(
            total_transactions=len(transactions), failed_count=len(failed), recovered_count=len(recovered),
            recovery_rate=round(len(recovered) / len(failed) * 100, 2) if failed else 0,
            total_failed_amount=round(sum(float(tx.amount) for tx in failed), 2),
            total_recovered_amount=round(sum(float(tx.recovered_amount or 0) for tx in recovered), 2),
            pending_retries=len(failed), avg_recovery_probability=round(sum(probabilities) / len(probabilities), 4) if probabilities else 0,
        )
    base = select(Transaction).where(Transaction.merchant_id == merchant.id)

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    failed_result = await db.execute(
        select(func.count()).where(
            Transaction.merchant_id == merchant.id, Transaction.status == "failed"
        )
    )
    failed = failed_result.scalar() or 0

    recovered_result = await db.execute(
        select(func.count()).where(
            Transaction.merchant_id == merchant.id,
            Transaction.recovered_amount.isnot(None),
        )
    )
    recovered = recovered_result.scalar() or 0

    captured_result = await db.execute(
        select(func.count()).where(
            Transaction.merchant_id == merchant.id, Transaction.status == "captured"
        )
    )
    captured = captured_result.scalar() or 0

    failed_amount_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.merchant_id == merchant.id, Transaction.status == "failed"
        )
    )
    failed_amount = float(failed_amount_result.scalar() or 0)

    recovered_amount_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.recovered_amount), 0)).where(
            Transaction.merchant_id == merchant.id,
            Transaction.recovered_amount.isnot(None),
        )
    )
    recovered_amount = float(recovered_amount_result.scalar() or 0)

    avg_prob_result = await db.execute(
        select(func.avg(MLPrediction.recovery_probability))
        .join(Transaction, MLPrediction.transaction_id == Transaction.id)
        .where(Transaction.merchant_id == merchant.id)
    )
    avg_prob = float(avg_prob_result.scalar() or 0)

    recovery_rate = (recovered / failed * 100) if failed > 0 else 0.0

    return DashboardSummary(
        total_transactions=total,
        failed_count=failed,
        recovered_count=recovered,
        recovery_rate=round(recovery_rate, 2),
        total_failed_amount=failed_amount,
        total_recovered_amount=recovered_amount,
        pending_retries=failed,
        avg_recovery_probability=round(avg_prob, 4),
    )


@router.get("/trend", response_model=list[TrendPoint])
async def get_trend(
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
    days: int = 30,
):
    from datetime import datetime, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            func.date(Transaction.created_at).label("date"),
            func.sum(case((Transaction.status == "failed", 1), else_=0)).label("failed"),
            func.sum(case((Transaction.recovered_amount.isnot(None), 1), else_=0)).label("recovered"),
        )
        .where(Transaction.merchant_id == merchant.id, Transaction.created_at >= cutoff)
        .group_by(func.date(Transaction.created_at))
        .order_by(func.date(Transaction.created_at))
    )

    points = []
    for row in result:
        failed = int(row.failed or 0)
        recovered = int(row.recovered or 0)
        rate = (recovered / failed * 100) if failed > 0 else 0.0
        points.append(
            TrendPoint(
                date=str(row.date),
                failed=failed,
                recovered=recovered,
                recovery_rate=round(rate, 2),
            )
        )
    return points


@router.get("/failure-breakdown", response_model=list[FailureBreakdownItem])
async def get_failure_breakdown(
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
):
    total_failed_result = await db.execute(
        select(func.count()).where(
            Transaction.merchant_id == merchant.id, Transaction.status == "failed"
        )
    )
    total_failed = total_failed_result.scalar() or 1

    result = await db.execute(
        select(
            Transaction.failure_reason,
            func.count().label("count"),
            func.avg(MLPrediction.recovery_probability).label("avg_prob"),
        )
        .outerjoin(MLPrediction, MLPrediction.transaction_id == Transaction.id)
        .where(Transaction.merchant_id == merchant.id, Transaction.status == "failed")
        .group_by(Transaction.failure_reason)
        .order_by(func.count().desc())
    )

    items = []
    for row in result:
        reason = row.failure_reason or "unknown"
        count = int(row.count)
        items.append(
            FailureBreakdownItem(
                reason=reason,
                count=count,
                percentage=round(count / total_failed * 100, 2),
                avg_recovery_probability=round(float(row.avg_prob or 0), 4),
            )
        )
    return items


@router.get("/strategy-comparison", response_model=StrategyComparison)
async def get_strategy_comparison(
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
    merchant_type: str | None = None,
    minimum_expected_value: float = 0.0,
):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.merchant_id == merchant.id, Transaction.status == "failed")
        .options(selectinload(Transaction.ml_predictions))
    )
    transactions = result.scalars().all()
    if merchant_type in MERCHANT_TYPES:
        transactions = [tx for tx in transactions if merchant_type_for(tx) == merchant_type]
    naive_revenue = 0.0
    recoverai_revenue = 0.0
    recoverai_costs = 0.0
    fatigue_counts = failure_counts_30d(transactions)
    for tx in transactions:
        prediction = tx.ml_predictions[-1] if tx.ml_predictions else None
        failure_count = fatigue_counts.get(tx.id, 0)
        probability = adjust_probability(prediction.recovery_probability, failure_count) if prediction else 0.0
        expected_revenue = probability * float(tx.amount)
        naive_revenue += expected_revenue
        recoverai_decision = decision_for(tx.amount, probability, tx.failure_reason, minimum_expected_value)
        if recoverai_decision["recommendation"] == "Retry":
            recoverai_revenue += expected_revenue
            recoverai_costs += RETRY_COST

    naive_costs = len(transactions) * RETRY_COST
    naive_net = naive_revenue - naive_costs
    recoverai_net = recoverai_revenue - recoverai_costs
    return StrategyComparison(
        naive={"recovered_revenue": round(naive_revenue, 2), "retry_costs": round(naive_costs, 2), "net_gain": round(naive_net, 2)},
        recoverai={"recovered_revenue": round(recoverai_revenue, 2), "retry_costs": round(recoverai_costs, 2), "net_gain": round(recoverai_net, 2)},
        net_gain_difference=round(recoverai_net - naive_net, 2),
        transactions_considered=len(transactions),
        retry_cost_per_attempt=RETRY_COST,
    )


@router.get("/ab-validation", response_model=ABValidation)
async def get_ab_validation(
    merchant: Merchant = Depends(get_current_merchant),
    db: AsyncSession = Depends(get_db),
    merchant_type: str | None = None,
):
    result = await db.execute(
        select(Transaction).where(Transaction.merchant_id == merchant.id, Transaction.status == "failed").options(selectinload(Transaction.ml_predictions))
    )
    transactions = list(result.scalars().all())
    if merchant_type in MERCHANT_TYPES:
        transactions = [tx for tx in transactions if merchant_type_for(tx) == merchant_type]
    transactions.sort(key=lambda tx: tx.id)
    fatigue_counts = failure_counts_30d(transactions)
    batches = []
    for index in range(5):
        batch = transactions[index::5]
        naive_net = -len(batch) * RETRY_COST
        recoverai_net = 0.0
        for tx in batch:
            prediction = tx.ml_predictions[-1] if tx.ml_predictions else None
            probability = adjust_probability(prediction.recovery_probability, fatigue_counts.get(tx.id, 0)) if prediction else 0.0
            naive_net += probability * float(tx.amount)
            decision = decision_for(tx.amount, probability, tx.failure_reason)
            if decision["recommendation"] == "Retry":
                recoverai_net += probability * float(tx.amount) - RETRY_COST
        batches.append({"batch": index + 1, "transactions": len(batch), "net_gain_difference": round(recoverai_net - naive_net, 2), "recoverai_wins": recoverai_net > naive_net})
    wins = sum(1 for batch in batches if batch["recoverai_wins"])
    return ABValidation(batches=batches, winning_batches=wins, average_advantage=round(sum(batch["net_gain_difference"] for batch in batches) / 5, 2))


@router.get("/feature-importances")
async def get_feature_importances(
    merchant: Merchant = Depends(get_current_merchant),
):
    return MLService.global_importances()
