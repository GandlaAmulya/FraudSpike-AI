from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.schemas import (
    CoarseGeography,
    FraudLabel,
    PaymentEvent,
    PaymentMethodType,
    PaymentStatus,
)


def _safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _merchant_history(events: list[PaymentEvent]) -> dict[str, list[PaymentEvent]]:
    grouped: dict[str, list[PaymentEvent]] = defaultdict(list)
    for event in sorted(events, key=lambda item: item.occurred_at):
        grouped[event.merchant_id].append(event)
    return grouped


def _risk_band(score: float) -> str:
    if score < 0.25:
        return "low"
    if score < 0.50:
        return "medium"
    if score < 0.75:
        return "high"
    return "critical"


def decision_for_score(score: float | Decimal) -> dict[str, Any]:
    numeric = float(score)
    if numeric < 0.25:
        return {
            "risk_level": "low",
            "decision": "approve",
            "threshold": 0.25,
            "reason": "Risk remains below the review threshold.",
        }
    if numeric < 0.5:
        return {
            "risk_level": "medium",
            "decision": "review",
            "threshold": 0.5,
            "reason": "The score crossed the manual-review threshold.",
        }
    if numeric < 0.85:
        return {
            "risk_level": "high",
            "decision": "hold",
            "threshold": 0.85,
            "reason": "The score indicates a high-risk transaction requiring intervention.",
        }
    return {
        "risk_level": "critical",
        "decision": "block",
        "threshold": 0.85,
        "reason": "The score exceeded the escalation threshold and should be escalated for a block recommendation.",
    }


def _merchant_fraud_rate(events: list[PaymentEvent]) -> Decimal:
    if not events:
        return Decimal("0")
    fraudulent = sum(1 for event in events if event.fraud_label is FraudLabel.FRAUDULENT)
    return (Decimal(fraudulent) / Decimal(len(events))).quantize(Decimal("0.000001"))


def score_transaction(event: PaymentEvent, historical_events: list[PaymentEvent]) -> dict[str, Any]:
    current_amount = event.amount
    history = list(historical_events)
    metadata = dict(event.metadata or {})
    baseline_amount = _safe_decimal(metadata.get("baseline_amount"), Decimal("250.00"))
    previous_fraud_rate = _safe_decimal(metadata.get("previous_fraud_rate"), Decimal("0.02"))
    current_fraud_rate = _safe_decimal(metadata.get("current_fraud_rate"), Decimal("0.03"))
    velocity_1h = int(metadata.get("velocity_1h", 0) or 0)
    velocity_24h = int(metadata.get("velocity_24h", 0) or 0)
    historical_transaction_count = int(metadata.get("historic_transaction_count", len(history) or 0) or 0)
    historical_fraud_count = int(metadata.get("historical_fraud_count", 0) or 0)

    previous_window = [item for item in history if item.occurred_at < event.occurred_at]
    merchant_rate = _merchant_fraud_rate(previous_window)
    baseline_average = (
        sum((item.amount for item in previous_window), Decimal("0")) / Decimal(len(previous_window))
        if previous_window
        else baseline_amount
    ).quantize(Decimal("0.01"))
    amount_ratio = Decimal("1")
    if baseline_average > 0:
        amount_ratio = current_amount / baseline_average

    if not previous_window:
        previous_fraud_rate = _safe_decimal(metadata.get("previous_fraud_rate"), Decimal("0.02"))
        current_fraud_rate = _safe_decimal(metadata.get("current_fraud_rate"), Decimal("0.18"))
        velocity_1h = max(velocity_1h, 4)
        velocity_24h = max(velocity_24h, 15)
        historical_transaction_count = max(historical_transaction_count, 1)
        historical_fraud_count = max(historical_fraud_count, 1)

    risk_score = Decimal("0.08")
    reasons: list[str] = []
    decision_path = "RULE_BASED"

    if len(history) < 5 and not previous_window:
        risk_score += Decimal("0.08")
        reasons.append("LOW_HISTORY")
        decision_path = "COLD_START_FALLBACK"

    if velocity_1h >= 4 or velocity_24h >= 12:
        risk_score += Decimal("0.22")
        reasons.append("HIGH_TRANSACTION_VELOCITY")

    if amount_ratio >= Decimal("3"):
        risk_score += Decimal("0.18")
        reasons.append("AMOUNT_ABOVE_BASELINE")
    elif amount_ratio >= Decimal("1.8"):
        risk_score += Decimal("0.10")
        reasons.append("ELEVATED_AMOUNT_DEVIATION")

    if current_fraud_rate > previous_fraud_rate + Decimal("0.10"):
        risk_score += Decimal("0.16")
        reasons.append("FRAUD_RATE_DEVIATION")

    if event.occurred_at.hour in {0, 1, 2, 3, 4, 22, 23}:
        risk_score += Decimal("0.08")
        reasons.append("UNUSUAL_TRANSACTION_TIME")

    if event.payment_method in {PaymentMethodType.CARD, PaymentMethodType.UPI} and velocity_24h >= 10:
        risk_score += Decimal("0.06")
        reasons.append("PAYMENT_METHOD_CONCENTRATION")

    if event.device_reference and previous_window:
        reused_devices = sum(1 for item in previous_window if item.device_reference == event.device_reference)
        if reused_devices >= 2:
            risk_score += Decimal("0.10")
            reasons.append("DEVICE_REUSE")
        elif reused_devices == 0:
            risk_score += Decimal("0.08")
            reasons.append("NEW_DEVICE")

    if event.geography and previous_window:
        geography_hits = sum(
            1 for item in previous_window if item.geography and item.geography.country_code == event.geography.country_code
        )
        if geography_hits == 0 and len(previous_window) >= 3:
            risk_score += Decimal("0.10")
            reasons.append("GEOGRAPHIC_MISMATCH")

    if merchant_rate >= Decimal("0.12"):
        risk_score += Decimal("0.10")
        reasons.append("HIGH_MERCHANT_FRAUD_RATE")

    if historical_fraud_count >= 2:
        risk_score += Decimal("0.08")
        reasons.append("CUSTOMER_HISTORY_RISK")

    risk_score = min(Decimal("0.98"), max(Decimal("0.04"), risk_score))
    if decision_path == "COLD_START_FALLBACK":
        risk_score = min(risk_score, Decimal("0.68"))
    normalized = float(risk_score)
    band = _risk_band(normalized)
    decision = decision_for_score(normalized)
    if not reasons:
        reasons = ["NORMAL_ACTIVITY_PATTERN"]

    confidence = 0.72 if decision_path == "COLD_START_FALLBACK" else 0.86
    if amount_ratio >= Decimal("2.5") or velocity_1h >= 5:
        confidence = min(0.98, confidence + 0.08)

    return {
        "risk_score": round(normalized, 4),
        "risk_level": band,
        "decision": decision["decision"],
        "decision_path": decision_path,
        "reasons": reasons[:5],
        "confidence": round(confidence, 3),
        "evidence": {
            "merchant_fraud_rate": str(merchant_rate),
            "amount_ratio": str(amount_ratio.quantize(Decimal("0.01"))),
            "velocity_1h": velocity_1h,
            "velocity_24h": velocity_24h,
            "baseline_amount": str(baseline_average),
            "current_amount": str(current_amount),
            "current_fraud_rate": str(current_fraud_rate.quantize(Decimal("0.000001"))),
            "previous_fraud_rate": str(previous_fraud_rate.quantize(Decimal("0.000001"))),
            "history_length": historical_transaction_count,
            "historical_fraud_count": historical_fraud_count,
        },
    }


def analyze_batch(events: list[PaymentEvent]) -> dict[str, Any]:
    grouped = _merchant_history(events)
    risk_results = []
    for merchant_id, merchant_events in grouped.items():
        for event in sorted(merchant_events, key=lambda item: item.occurred_at):
            history = [item for item in merchant_events if item.occurred_at < event.occurred_at]
            risk_results.append({"merchant_id": merchant_id, **score_transaction(event, history)})

    high_risk = sum(1 for row in risk_results if row["risk_level"] in {"high", "critical"})
    medium_risk = sum(1 for row in risk_results if row["risk_level"] == "medium")
    low_risk = sum(1 for row in risk_results if row["risk_level"] == "low")
    average_risk = sum(float(row["risk_score"]) for row in risk_results) / len(risk_results) if risk_results else 0.0
    fraud_rate = (
        sum(1 for row in risk_results if row["decision"] in {"hold", "block"}) / len(risk_results)
        if risk_results
        else 0.0
    )
    merchants = sorted({row["merchant_id"] for row in risk_results})
    top_risk = sorted(
        ({"merchant_id": merchant_id, "average_risk": sum(float(item["risk_score"]) for item in risk_results if item["merchant_id"] == merchant_id) / max(1, sum(1 for item in risk_results if item["merchant_id"] == merchant_id))} for merchant_id in merchants),
        key=lambda item: item["average_risk"],
        reverse=True,
    )[:5]

    return {
        "records_processed": len(events),
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "low_risk": low_risk,
        "fraud_rate": round(fraud_rate, 4),
        "average_risk": round(average_risk, 4),
        "merchants_affected": len(merchants),
        "top_risk_merchants": top_risk,
    }
