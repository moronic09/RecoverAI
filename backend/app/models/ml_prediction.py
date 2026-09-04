from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    predicted_failure_class: Mapped[str] = mapped_column(String(64))
    failure_confidence: Mapped[float] = mapped_column(Float)
    recovery_probability: Mapped[float] = mapped_column(Float)
    recommended_action: Mapped[str] = mapped_column(String(64))
    feature_importances: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transaction: Mapped["Transaction"] = relationship(back_populates="ml_predictions")
