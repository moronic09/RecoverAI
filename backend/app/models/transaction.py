from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    razorpay_payment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(32), index=True)  # failed, captured, pending
    payment_method: Mapped[str] = mapped_column(String(32))  # card, upi, netbanking, wallet
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    customer_failure_history: Mapped[int] = mapped_column(Integer, default=0)
    recovered_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    merchant: Mapped["Merchant"] = relationship(back_populates="transactions")
    recovery_attempts: Mapped[list["RecoveryAttempt"]] = relationship(back_populates="transaction")
    ml_predictions: Mapped[list["MLPrediction"]] = relationship(back_populates="transaction")
