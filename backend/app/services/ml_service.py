import sys
from pathlib import Path

# Add ml directory to path for inference
ML_DIR = Path(__file__).resolve().parent.parent.parent.parent / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from predict import predict_transaction, get_global_feature_importances  # noqa: E402

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ml_prediction import MLPrediction
from app.models.transaction import Transaction


class MLService:
    @staticmethod
    def predict(tx: Transaction) -> dict:
        tx_dict = {
            "amount": float(tx.amount),
            "payment_method": tx.payment_method,
            "created_at": tx.created_at.isoformat() if tx.created_at else datetime.now(timezone.utc).isoformat(),
            "retry_count": tx.retry_count,
            "customer_failure_history": tx.customer_failure_history,
            "bank_code": tx.bank_code,
            "status": tx.status,
            "failure_reason": tx.failure_reason,
        }
        return predict_transaction(tx_dict)

    @staticmethod
    async def predict_and_store(db: AsyncSession, tx: Transaction) -> MLPrediction:
        result = MLService.predict(tx)
        prediction = MLPrediction(
            transaction_id=tx.id,
            predicted_failure_class=result["predicted_failure_class"],
            failure_confidence=result["failure_confidence"],
            recovery_probability=result["recovery_probability"],
            recommended_action=result["recommended_action"],
            feature_importances=result.get("feature_importances"),
        )
        db.add(prediction)
        await db.flush()
        return prediction

    @staticmethod
    def global_importances() -> dict:
        return get_global_feature_importances()
