from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class MerchantRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=2)


class MerchantLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MerchantResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: int
    razorpay_payment_id: str
    amount: Decimal
    currency: str
    status: str
    payment_method: str
    failure_reason: str | None
    failure_code: str | None
    customer_id: str
    customer_email: str | None
    retry_count: int
    customer_failure_history: int
    recovered_amount: Decimal | None
    created_at: datetime
    latest_prediction: "MLPredictionResponse | None" = None
    estimated_retry_cost: float | None = None
    expected_value: float | None = None
    recommendation: str | None = None
    recommendation_reason: str | None = None
    recommended_channel: str | None = None
    recommended_channel_label: str | None = None
    customer_failure_count_30d: int = 0
    fatigue_adjusted_probability: float | None = None
    confidence: str | None = None
    explainability: list[dict[str, str]] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MLPredictionResponse(BaseModel):
    id: int
    predicted_failure_class: str
    failure_confidence: float
    recovery_probability: float
    recommended_action: str
    feature_importances: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PredictResponse(BaseModel):
    transaction_id: int
    predicted_failure_class: str
    failure_confidence: float
    recovery_probability: float
    recommended_action: str
    feature_importances: dict[str, float]
    feature_values: dict[str, float]
    recommended_channel: str
    confidence: str
    explainability: list[dict[str, str]]
    customer_failure_count_30d: int


class RetryResponse(BaseModel):
    transaction_id: int
    task_id: str
    message: str
    scheduled_at: datetime | None


class RecoveryAttemptResponse(BaseModel):
    id: int
    attempt_number: int
    status: str
    channel: str
    outcome: str | None
    scheduled_at: datetime | None
    executed_at: datetime | None

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    total_transactions: int
    failed_count: int
    recovered_count: int
    recovery_rate: float
    total_failed_amount: float
    total_recovered_amount: float
    pending_retries: int
    avg_recovery_probability: float


class StrategyMetrics(BaseModel):
    recovered_revenue: float
    retry_costs: float
    net_gain: float


class StrategyComparison(BaseModel):
    naive: StrategyMetrics
    recoverai: StrategyMetrics
    net_gain_difference: float
    transactions_considered: int
    retry_cost_per_attempt: float


class ABValidationBatch(BaseModel):
    batch: int
    transactions: int
    net_gain_difference: float
    recoverai_wins: bool


class ABValidation(BaseModel):
    batches: list[ABValidationBatch]
    winning_batches: int
    average_advantage: float


class TrendPoint(BaseModel):
    date: str
    failed: int
    recovered: int
    recovery_rate: float


class FailureBreakdownItem(BaseModel):
    reason: str
    count: int
    percentage: float
    avg_recovery_probability: float


class LiveEvent(BaseModel):
    event_type: str
    transaction_id: int
    data: dict[str, Any]
    timestamp: datetime


class SimulationToggle(BaseModel):
    enabled: bool
