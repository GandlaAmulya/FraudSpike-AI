from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import (
    AnalysisWindow,
    AuditEvent,
    AuditEventType,
    CoarseGeography,
    EvaluationResult,
    EvidenceCategory,
    EvidenceItem,
    FraudLabel,
    FraudSpikeIncident,
    IncidentSeverity,
    IncidentStatus,
    Investigation,
    InvestigationStatus,
    PaymentEvent,
    PaymentMethodType,
    PaymentStatus,
    VerificationResult,
)

UTC_TZ = UTC
IST = timezone(timedelta(hours=5, minutes=30))


def valid_payment_event() -> PaymentEvent:
    return PaymentEvent(
        event_id="evt-001",
        merchant_id="merchant-001",
        occurred_at=datetime(2026, 8, 29, 12, 0, tzinfo=IST),
        amount=Decimal("1250.50"),
        currency="INR",
        payment_method=PaymentMethodType.UPI,
        payment_status=PaymentStatus.CAPTURED,
        customer_reference="customer-token-001",
        device_reference="device-token-001",
        geography=CoarseGeography(country_code="IN", region_code="KA"),
        metadata={"channel": "checkout", "retry_count": 0},
    )


def test_payment_event_has_required_fields_and_normalizes_to_utc() -> None:
    event = valid_payment_event()

    assert event.fraud_label is FraudLabel.UNKNOWN
    assert event.occurred_at.tzinfo == UTC_TZ
    assert event.occurred_at.hour == 6
    assert event.amount == Decimal("1250.50")


def test_payment_event_rejects_missing_required_fields() -> None:
    payload = valid_payment_event().model_dump()
    del payload["merchant_id"]

    with pytest.raises(ValidationError):
        PaymentEvent.model_validate(payload)


def test_payment_event_rejects_invalid_enum_and_currency() -> None:
    payload = valid_payment_event().model_dump()

    with pytest.raises(ValidationError):
        PaymentEvent.model_validate({**payload, "fraud_label": "suspicious"})

    with pytest.raises(ValidationError):
        PaymentEvent.model_validate({**payload, "currency": "rupees"})


def test_payment_event_rejects_naive_timestamp_and_invalid_amount() -> None:
    payload = valid_payment_event().model_dump()

    with pytest.raises(ValidationError):
        PaymentEvent.model_validate(
            {**payload, "occurred_at": datetime(2026, 8, 29, 12, 0)},
        )

    with pytest.raises(ValidationError):
        PaymentEvent.model_validate({**payload, "amount": Decimal("-1.00")})


def test_analysis_window_rejects_reversed_bounds() -> None:
    start = datetime(2026, 8, 29, 12, tzinfo=UTC)

    with pytest.raises(ValidationError):
        AnalysisWindow(
            start_at=start,
            end_at=start - timedelta(minutes=1),
        )


def test_incident_and_evidence_contracts_validate_typed_values() -> None:
    window = AnalysisWindow(
        start_at=datetime(2026, 8, 29, 12, tzinfo=UTC_TZ),
        end_at=datetime(2026, 8, 29, 13, tzinfo=UTC_TZ),
    )
    incident = FraudSpikeIncident(
        incident_id="incident-001",
        merchant_id="merchant-001",
        detected_at=datetime(2026, 8, 29, 13, tzinfo=UTC),
        analysis_window=window,
        baseline_fraud_rate=Decimal("0.010000"),
        observed_fraud_rate=Decimal("0.080000"),
        deviation=Decimal("0.070000"),
        affected_transaction_count=12,
        severity=IncidentSeverity.HIGH,
        detector_version="detector-v1",
        confidence=Decimal("0.900000"),
    )
    evidence = EvidenceItem(
        evidence_id="evidence-001",
        incident_id=incident.incident_id,
        category=EvidenceCategory.MERCHANT_BASELINE,
        metric="observed_fraud_rate",
        value=Decimal("0.080000"),
        baseline_value=Decimal("0.010000"),
        supporting_event_ids=["evt-001"],
        window=window,
    )

    assert incident.status is IncidentStatus.DETECTED
    assert evidence.incident_id == incident.incident_id


def test_investigation_rejects_end_before_start() -> None:
    started_at = datetime(2026, 8, 29, 13, tzinfo=UTC_TZ)

    with pytest.raises(ValidationError):
        Investigation(
            investigation_id="investigation-001",
            incident_id="incident-001",
            status=InvestigationStatus.COMPLETED,
            started_at=started_at,
            ended_at=started_at - timedelta(seconds=1),
        )


def test_evaluation_metrics_are_nullable_until_calculated() -> None:
    result = EvaluationResult(
        evaluation_id="evaluation-001",
        dataset_version="dataset-v1",
        held_out_test_set_id="held-out-v1",
        detector_version="detector-v1",
    )

    assert result.true_positives is None
    assert result.precision is None
    assert result.recall is None
    assert result.f1 is None
    assert result.false_positive_cost is None
    assert result.evaluated_at is None


def test_evaluation_rejects_invalid_metric_and_count_values() -> None:
    base = {
        "evaluation_id": "evaluation-001",
        "dataset_version": "dataset-v1",
        "held_out_test_set_id": "held-out-v1",
        "detector_version": "detector-v1",
    }

    with pytest.raises(ValidationError):
        EvaluationResult.model_validate({**base, "precision": Decimal("1.10")})

    with pytest.raises(ValidationError):
        EvaluationResult.model_validate({**base, "false_positives": -1})

    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(
            {
                **base,
                "false_positives": 2,
                "false_positive_count": 1,
            },
        )


def test_payment_event_serializes_and_deserializes_without_losing_money() -> None:
    event = valid_payment_event()
    serialized = event.model_dump(mode="json")
    restored = PaymentEvent.model_validate(serialized)

    assert serialized["amount"] == "1250.50"
    assert serialized["occurred_at"].endswith("Z")
    assert restored.amount == Decimal("1250.50")
    assert restored.occurred_at == event.occurred_at


def test_audit_event_requires_actor_or_source_and_is_immutable() -> None:
    event = AuditEvent(
        event_id="audit-001",
        occurred_at=datetime(2026, 8, 29, 13, tzinfo=IST),
        event_type=AuditEventType.DETECTION,
        source="detector-v1",
        incident_id="incident-001",
        action="incident_created",
        details={"reason": "threshold_exceeded"},
    )

    assert event.occurred_at.tzinfo == UTC_TZ

    with pytest.raises(ValidationError):
        AuditEvent(
            event_id="audit-002",
            occurred_at=datetime(2026, 8, 29, 13, tzinfo=UTC_TZ),
            event_type=AuditEventType.SYSTEM,
            action="invalid_without_actor_or_source",
        )

    with pytest.raises(ValidationError):
        event.action = "changed"


def test_unknown_fraud_label_can_be_explicitly_preserved() -> None:
    event = valid_payment_event().model_copy(
        update={"fraud_label": FraudLabel.UNKNOWN},
    )

    assert event.fraud_label is FraudLabel.UNKNOWN
    assert VerificationResult.INCONCLUSIVE.value == "inconclusive"