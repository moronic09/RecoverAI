"""Cost-aware recovery decisions built on persisted ML probabilities."""

from decimal import Decimal

RETRY_COST = 2.0
MINIMUM_EXPECTED_VALUE = 0.0


def channel_for(failure_reason: str | None, recovery_probability: float, expected_value: float) -> str:
    if expected_value <= MINIMUM_EXPECTED_VALUE:
        return "skip"
    reason = failure_reason or ""
    if reason in {"network_error", "timeout", "bank_declined"}:
        return "silent_retry"
    if reason == "card_expired":
        return "nudge_email"
    if reason == "insufficient_funds":
        return "nudge_whatsapp" if recovery_probability >= 0.35 else "nudge_sms"
    if reason in {"invalid_card", "authentication_failed"}:
        return "nudge_sms"
    return "in_app_banner"


def channel_label(channel: str) -> str:
    return {
        "silent_retry": "Silent retry",
        "nudge_sms": "SMS nudge",
        "nudge_whatsapp": "WhatsApp nudge",
        "nudge_email": "Email nudge",
        "in_app_banner": "In-app banner",
        "skip": "Skip",
    }.get(channel, channel.replace("_", " ").title())


def decision_for(
    amount: Decimal | float,
    recovery_probability: float,
    failure_reason: str | None = None,
    minimum_expected_value: float = MINIMUM_EXPECTED_VALUE,
) -> dict[str, float | str]:
    amount_value = float(amount)
    probability = max(0.0, min(1.0, float(recovery_probability)))
    expected_value = (probability * amount_value) - RETRY_COST
    recommendation = "Retry" if expected_value > minimum_expected_value else "Skip"
    recommended_channel = channel_for(failure_reason, probability, expected_value)
    if recommendation == "Retry":
        reason = (
            f"Retry: {probability:.0%} recovery chance x ₹{amount_value:,.2f} = "
            f"₹{probability * amount_value:,.2f} expected revenue, less ₹{RETRY_COST:.2f} retry cost."
        )
    else:
        reason = (
            f"Skipped: {probability:.0%} recovery chance x ₹{amount_value:,.2f} = "
            f"₹{probability * amount_value:,.2f} expected revenue, not enough to justify the ₹{RETRY_COST:.2f} retry cost."
        )
    return {
        "estimated_retry_cost": RETRY_COST,
        "expected_value": round(expected_value, 2),
        "recommendation": recommendation,
        "recommended_channel": recommended_channel,
        "recommended_channel_label": channel_label(recommended_channel),
        "recommendation_reason": reason,
    }