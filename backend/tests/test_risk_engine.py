from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.schemas import (
    CoarseGeography,
    FraudLabel,
    PaymentEvent,
    PaymentMethodType,
    PaymentStatus,
)
from app.services.risk_engine import analyze_batch, decision_for_score, score_transaction


def _event(**overrides):
    defaults = {
        "event_id": "evt-test-001",
        "merchant_id": "merchant-099",
        "occurred_at": datetime(2025, 6, 12, 14, 30, tzinfo=UTC),
        "amount": Decimal("2400.00"),
        "currency": "INR",
        "payment_method": PaymentMethodType.CARD,
        "payment_status": PaymentStatus.CAPTURED,
        "customer_reference": "customer-111",
        "device_reference": "device-222",
        "geography": CoarseGeography(country_code="IN", region_code="KA"),
        "fraud_label": FraudLabel.UNKNOWN,
        "metadata": {
            "historic_transaction_count": 12,
            "historical_fraud_count": 1,
            "velocity_1h": 4,
            "velocity_24h": 15,
            "baseline_amount": Decimal("420.00"),
            "current_amount": Decimal("2400.00"),
            "current_fraud_rate": Decimal("0.18"),
            "previous_fraud_rate": Decimal("0.02"),
        },
    }
    payload = {**defaults, **overrides}
    return PaymentEvent(**payload)


def test_score_transaction_for_high_velocity_is_high_risk() -> None:
    history = [
        _event(event_id=f"evt-{index}", amount=Decimal("350.00"), occurred_at=datetime(2025, 6, 11, 15, 0, tzinfo=UTC))
        for index in range(1, 8)
    ]
    event = _event(event_id="evt-urgent", amount=Decimal("4800.00"), customer_reference="customer-999")

    result = score_transaction(event, history)

    assert result["risk_score"] >= 0.6
    assert result["risk_level"] in {"high", "critical"}
    assert "HIGH_TRANSACTION_VELOCITY" in result["reasons"]
    assert result["decision_path"] == "RULE_BASED"


def test_score_transaction_uses_cold_start_fallback_for_low_history() -> None:
    event = _event(event_id="evt-cold", merchant_id="merchant-new")

    result = score_transaction(event, [])

    assert result["decision_path"] == "COLD_START_FALLBACK"
    assert result["risk_level"] in {"medium", "high"}
    assert result["decision"] in {"review", "hold"}


def test_decision_policy_maps_scores_to_expected_actions() -> None:
    assert decision_for_score(0.12)["decision"] == "approve"
    assert decision_for_score(0.42)["decision"] == "review"
    assert decision_for_score(0.82)["decision"] == "hold"


def test_analyze_batch_reports_summary_counts() -> None:
    events = [
        _event(event_id="evt-low", amount=Decimal("100.00"), merchant_id="merchant-1"),
        _event(event_id="evt-mid", amount=Decimal("900.00"), merchant_id="merchant-1"),
        _event(event_id="evt-high", amount=Decimal("4500.00"), merchant_id="merchant-2"),
    ]

    summary = analyze_batch(events)

    assert summary["records_processed"] == 3
    assert summary["high_risk"] >= 1
    assert summary["average_risk"] > 0
