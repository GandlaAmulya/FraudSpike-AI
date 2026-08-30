from decimal import Decimal

from app.detectors.fraud_spike import detect_merchant_spikes
from app.schemas import FraudLabel
from app.services.dataset import build_demo_dataset, split_events_by_period


def test_detect_merchant_spikes_rounds_probability_values_to_contract_precision() -> None:
    split = split_events_by_period(build_demo_dataset())
    events = split["train"] + split["validation"] + split["test"]

    incidents = detect_merchant_spikes(events)

    assert incidents
    for incident in incidents:
        assert incident.baseline_fraud_rate <= Decimal("1")
        assert incident.observed_fraud_rate <= Decimal("1")
        assert incident.baseline_fraud_rate.as_tuple().exponent >= -6
        assert incident.observed_fraud_rate.as_tuple().exponent >= -6


def test_detect_merchant_spikes_catches_known_synthetic_injection() -> None:
    split = split_events_by_period(build_demo_dataset())
    events = split["train"] + split["validation"] + split["test"]

    incidents = detect_merchant_spikes(events)
    merchants = {incident.merchant_id for incident in incidents}

    assert "merchant-005" in merchants
    assert any(
        incident.merchant_id == "merchant-005"
        and incident.observed_fraud_rate > incident.baseline_fraud_rate
        for incident in incidents
    )
    suspicious = [incident for incident in incidents if incident.merchant_id == "merchant-005"]
    assert suspicious
    assert any(
        item.analysis_window.start_at >= split["train"][0].occurred_at
        and item.analysis_window.start_at <= split["test"][-1].occurred_at
        for item in suspicious
    )


def test_held_out_split_contains_real_fraudulent_events() -> None:
    split = split_events_by_period(build_demo_dataset())

    suspicious_test_events = [
        event for event in split["test"] if event.merchant_id in {"merchant-002", "merchant-005"}
    ]

    assert suspicious_test_events
    assert any(event.fraud_label is FraudLabel.FRAUDULENT for event in suspicious_test_events)


def test_detect_merchant_spikes_catches_real_held_out_fraud_window() -> None:
    split = split_events_by_period(build_demo_dataset())
    full_events = split["train"] + split["validation"] + split["test"]

    incidents = detect_merchant_spikes(full_events)
    suspicious = [incident for incident in incidents if incident.merchant_id == "merchant-005"]

    assert suspicious
    assert any(
        incident.observed_fraud_rate >= Decimal("0.20")
        and incident.affected_transaction_count >= 20
        for incident in suspicious
    )
