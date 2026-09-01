from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.schemas import (
    AnalysisWindow,
    FraudLabel,
    FraudSpikeIncident,
    IncidentSeverity,
    IncidentStatus,
    PaymentEvent,
    PaymentMethodType,
    PaymentStatus,
)
from app.services.investigation import build_investigation_for_incident
from app.services.local_ml import LocalAnomalyAgent


def _incident() -> FraudSpikeIncident:
    now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    return FraudSpikeIncident(
        incident_id="incident-ml-001",
        merchant_id="merchant-ml-001",
        detected_at=now,
        analysis_window=AnalysisWindow(
            start_at=now - timedelta(minutes=20),
            end_at=now,
        ),
        baseline_fraud_rate=Decimal("0.08"),
        observed_fraud_rate=Decimal("0.35"),
        deviation=Decimal("0.27"),
        affected_transaction_count=21,
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.DETECTED,
        detector_version="merchant-fraud-spike-v1",
        confidence=Decimal("0.92"),
        risk_score=Decimal("0.72"),
        evidence=[],
        suspicious_event_ids=["evt-1", "evt-2", "evt-3"],
        investigation_notes=[],
        resolution=None,
        created_at=now,
        updated_at=now,
    )


def _merchant_events() -> list[PaymentEvent]:
    start = datetime(2026, 9, 1, 11, 0, tzinfo=UTC)
    events: list[PaymentEvent] = []
    for index in range(18):
        occurred = start + timedelta(minutes=index * 3)
        label = FraudLabel.FRAUDULENT if index % 3 == 0 else FraudLabel.LEGITIMATE
        amount = Decimal("1500.00") if label is FraudLabel.FRAUDULENT else Decimal("380.00")
        events.append(
            PaymentEvent(
                event_id=f"evt-{index}",
                merchant_id="merchant-ml-001",
                occurred_at=occurred,
                amount=amount,
                currency="INR",
                payment_method=PaymentMethodType.UPI if index % 2 == 0 else PaymentMethodType.CARD,
                payment_status=PaymentStatus.CAPTURED,
                customer_reference=f"customer-{index}",
                device_reference=f"device-{index % 4}",
                geography={"country_code": "IN", "region_code": "KA"},
                fraud_label=label,
                metadata={"channel": "checkout", "retry_count": 1},
            )
        )
    return events


def test_local_anomaly_model_scores_real_transaction_history() -> None:
    agent = LocalAnomalyAgent()
    result = agent.analyze(_merchant_events())

    assert result["available"] is True
    assert result["model"] == "IsolationForest"
    assert result["model_version"] == "local-isolation-forest-v1"
    assert result["assessment"] in {"ANOMALOUS", "NOT_ANOMALOUS"}
    assert result["evidence_references"]


def test_investigation_includes_ml_assessment_and_valid_evidence_references() -> None:
    investigation = build_investigation_for_incident(
        _incident(),
        merchant_events=_merchant_events(),
    )

    assert investigation.incident_id == "incident-ml-001"
    assert investigation.provider == "local-anomaly-analysis"
    assert investigation.ml_assessment is not None
    assert investigation.ml_assessment["available"] is True
    assert investigation.ml_assessment["evidence_references"]
    assert any(ref.startswith("transaction:") for ref in investigation.ml_assessment["evidence_references"])
    assert any("anomaly" in finding.lower() for finding in investigation.findings)
    assert investigation.recommended_action in {"INVESTIGATE", "VERIFY", "HOLD"}


def test_investigation_handles_cold_start_without_fabricating_evidence() -> None:
    incident = _incident()
    insufficient = build_investigation_for_incident(incident, merchant_events=[])

    assert insufficient.risk_level == "LOW"
    assert insufficient.ml_assessment is not None
    assert insufficient.ml_assessment["available"] is False
    assert "insufficient evidence" in insufficient.reasoning_summary.lower()
    assert insufficient.limitations
