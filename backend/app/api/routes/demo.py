from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db.database import session_factory
from app.detectors.fraud_spike import detect_merchant_spikes
from app.evaluation import evaluate_held_out_predictions
from app.integrations.razorpay import get_razorpay_status
from app.models import AuditEventModel, FraudSpikeIncidentModel, InvestigationModel, PaymentEventModel
from app.schemas import (
    AuditEvent,
    AuditEventType,
    FraudLabel,
    FraudSpikeIncident,
    IncidentStatus,
    Investigation,
    PaymentEvent,
    VerificationResult,
)
from app.services.dataset import build_demo_dataset, split_events_by_period
from app.services.investigation import build_investigation_for_incident, verify_investigation_claims
from app.services.storage import (
    get_dashboard_summary,
    list_incidents,
    persist_audit_event,
    persist_incident,
    persist_investigation,
    persist_payment_events,
)

router = APIRouter()


def _dataset_key() -> dict[str, list[PaymentEvent]]:
    events = build_demo_dataset()
    return split_events_by_period(events)


def _detected_incidents() -> list[FraudSpikeIncident]:
    split = _dataset_key()
    events = split["train"] + split["validation"] + split["test"]
    return detect_merchant_spikes(events)


async def _create_audit_record(
    *,
    incident_id: str | None = None,
    investigation_id: str | None = None,
    action: str,
    details: dict[str, object],
    source: str = "fraudspike-api",
) -> None:
    event = AuditEvent(
        event_id=f"audit-{incident_id or investigation_id or source}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}",
        occurred_at=datetime.now(UTC),
        event_type=AuditEventType.SYSTEM,
        source=source,
        incident_id=incident_id,
        investigation_id=investigation_id,
        action=action,
        details=details,
    )
    async with session_factory() as session:
        await persist_audit_event(session, event)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "fraudspike-backend"}


@router.post("/events")
async def create_event(event: PaymentEvent) -> PaymentEvent:
    async with session_factory() as session:
        await persist_payment_events(session, [event])
    await _create_audit_record(
        incident_id=None,
        action="event_ingested",
        details={"merchant_id": event.merchant_id, "event_id": event.event_id, "fraud_label": event.fraud_label.value},
    )
    return event


@router.get("/merchants")
async def list_merchants() -> list[str]:
    split = _dataset_key()
    events = split["train"] + split["validation"] + split["test"]
    return sorted({event.merchant_id for event in events})


@router.get("/merchants/{merchant_id}")
async def get_merchant(merchant_id: str) -> dict[str, object]:
    split = _dataset_key()
    events = split["train"] + split["validation"] + split["test"]
    merchant_events = [event for event in events if event.merchant_id == merchant_id]
    if not merchant_events:
        raise HTTPException(status_code=404, detail="Merchant not found")
    fraud_count = sum(1 for event in merchant_events if event.fraud_label is FraudLabel.FRAUDULENT)
    return {
        "merchant_id": merchant_id,
        "total_transactions": len(merchant_events),
        "fraudulent_transactions": fraud_count,
        "risk_score": round((fraud_count / len(merchant_events)), 4) if merchant_events else 0,
        "baseline_vs_current": {
            "baseline_fraud_rate": "0.02",
            "current_fraud_rate": str((Decimal(fraud_count) / Decimal(len(merchant_events))).quantize(Decimal("0.000001"))),
        },
    }


@router.post("/detect")
async def detect_events() -> list[FraudSpikeIncident]:
    return _detected_incidents()


@router.get("/evaluation")
async def evaluation() -> dict[str, object]:
    split = _dataset_key()
    dataset_events = split["train"] + split["validation"] + split["test"]
    incidents = detect_merchant_spikes(dataset_events)
    merchant_predictions = {incident.merchant_id: True for incident in incidents}
    actual: list[int] = []
    predicted: list[int] = []
    for event in split["test"]:
        actual.append(1 if event.fraud_label is FraudLabel.FRAUDULENT else 0)
        predicted.append(1 if merchant_predictions.get(event.merchant_id, False) else 0)
    result = evaluate_held_out_predictions(
        actual,
        predicted,
        dataset_version="synthetic-demo-v1",
        held_out_test_set_id="test-period-v1",
        detector_version="merchant-fraud-spike-v1",
        false_positive_cost_per_case=Decimal("125.00"),
    )
    return {
        "test_set_size": result.test_set_size,
        "tp": result.true_positives,
        "tn": result.true_negatives,
        "fp": result.false_positives,
        "fn": result.false_negatives,
        "precision": str(result.precision),
        "recall": str(result.recall),
        "f1": str(result.f1),
        "confusion_matrix": result.confusion_matrix,
        "false_positive_cost": str(result.false_positive_cost),
    }


@router.get("/demo/dataset")
async def demo_dataset() -> dict[str, int]:
    split = _dataset_key()
    return {
        "train": len(split["train"]),
        "validation": len(split["validation"]),
        "test": len(split["test"]),
    }


@router.post("/demo/seed")
async def demo_seed() -> dict[str, object]:
    events = build_demo_dataset()
    async with session_factory() as session:
        await persist_payment_events(session, events)
    return {
        "status": "seeded",
        "total_events": len(events),
        "merchants": sorted({event.merchant_id for event in events}),
    }


@router.get("/payments")
async def list_payments() -> list[PaymentEvent]:
    async with session_factory() as session:
        rows = (await session.execute(select(PaymentEventModel))).scalars().all()
        return [
            PaymentEvent(
                event_id=row.event_id,
                merchant_id=row.merchant_id,
                occurred_at=row.occurred_at,
                amount=row.amount,
                currency=row.currency,
                payment_method=row.payment_method,
                payment_status=row.payment_status,
                customer_reference=row.customer_reference,
                device_reference=row.device_reference,
                geography=(
                    None
                    if row.geography_country is None and row.geography_region is None
                    else {"country_code": row.geography_country, "region_code": row.geography_region}
                ),
                fraud_label=row.fraud_label,
                metadata=json.loads(row.metadata_json or "{}"),
            )
            for row in rows
        ]


@router.post("/payments")
async def create_payment(event: PaymentEvent) -> PaymentEvent:
    async with session_factory() as session:
        await persist_payment_events(session, [event])
    return event


@router.get("/demo/detections")
async def demo_detections() -> list[FraudSpikeIncident]:
    return _detected_incidents()


@router.get("/detections")
async def list_detections() -> list[FraudSpikeIncident]:
    return _detected_incidents()


@router.post("/incidents")
async def create_incident(incident: FraudSpikeIncident) -> FraudSpikeIncident:
    incident.created_at = incident.created_at or incident.detected_at
    incident.updated_at = incident.updated_at or incident.detected_at
    async with session_factory() as session:
        await persist_incident(session, incident)
    await _create_audit_record(
        incident_id=incident.incident_id,
        action="incident_created",
        details={"merchant_id": incident.merchant_id, "severity": incident.severity.value, "risk_score": str(incident.risk_score or incident.observed_fraud_rate)},
    )
    return incident


@router.get("/dashboard/summary")
async def dashboard_summary() -> dict[str, object]:
    split = _dataset_key()
    all_events = split["train"] + split["validation"] + split["test"]
    incidents = _detected_incidents()
    total_transactions = len(all_events)
    total_fraud = sum(
        1 for event in all_events if event.fraud_label is FraudLabel.FRAUDULENT
    )
    severity_breakdown = {
        "critical": sum(1 for incident in incidents if incident.severity.value == "critical"),
        "high": sum(1 for incident in incidents if incident.severity.value == "high"),
        "medium": sum(1 for incident in incidents if incident.severity.value == "medium"),
        "low": sum(1 for incident in incidents if incident.severity.value == "low"),
    }
    merchant_risk = []
    grouped: dict[str, list[PaymentEvent]] = {}
    for event in all_events:
        grouped.setdefault(event.merchant_id, []).append(event)
    for merchant_id, merchant_events in grouped.items():
        fraud_count = sum(
            1 for event in merchant_events if event.fraud_label is FraudLabel.FRAUDULENT
        )
        merchant_risk.append(
            {
                "merchant_id": merchant_id,
                "total_transactions": len(merchant_events),
                "fraudulent_transactions": fraud_count,
                "fraud_rate": round((fraud_count / len(merchant_events)), 4) if merchant_events else 0,
            }
        )
    merchant_risk.sort(key=lambda item: item["fraud_rate"], reverse=True)

    false_positive_cost_estimate = Decimal(total_fraud) * Decimal("125.00")
    return {
        "total_transactions": total_transactions,
        "fraud_rate": round((total_fraud / total_transactions), 4) if total_transactions else 0,
        "active_incidents": len(incidents),
        "severity_breakdown": severity_breakdown,
        "merchant_risk_ranking": merchant_risk[:5],
        "false_positive_cost_estimate": str(false_positive_cost_estimate.quantize(Decimal("0.01"))),
    }


@router.get("/dashboard/metrics")
async def dashboard_metrics() -> dict[str, object]:
    return await dashboard_summary()


@router.get("/incidents")
async def list_incidents() -> list[FraudSpikeIncident]:
    return _detected_incidents()


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> FraudSpikeIncident:
    incidents = _detected_incidents()
    incident = next((item for item in incidents if item.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/investigate")
async def investigate_incident(incident_id: str) -> Investigation:
    incidents = _detected_incidents()
    incident = next((item for item in incidents if item.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    investigation = build_investigation_for_incident(incident)
    async with session_factory() as session:
        await persist_investigation(session, investigation)
    await _create_audit_record(
        incident_id=incident_id,
        investigation_id=investigation.investigation_id,
        action="investigation_started",
        details={"merchant_id": incident.merchant_id, "status": investigation.status.value},
    )
    return investigation


@router.post("/incidents/{incident_id}/action")
async def incident_action(incident_id: str, action: str = Query(...), notes: str | None = None) -> FraudSpikeIncident:
    incidents = _detected_incidents()
    incident = next((item for item in incidents if item.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if notes:
        incident.investigation_notes.append(notes)
    if action == "verify":
        incident.status = IncidentStatus.VERIFIED
    elif action == "dismiss":
        incident.status = IncidentStatus.DISMISSED
    elif action == "resolve":
        incident.status = IncidentStatus.RESOLVED
    else:
        incident.status = IncidentStatus.INVESTIGATING
    incident.updated_at = datetime.now(UTC)
    await _create_audit_record(
        incident_id=incident_id,
        action=f"incident_{action}",
        details={"merchant_id": incident.merchant_id, "status": incident.status.value, "notes": notes or ""},
    )
    return incident


@router.get("/incidents/{incident_id}/audit")
async def incident_audit(incident_id: str) -> list[dict[str, object]]:
    async with session_factory() as session:
        rows = (await session.execute(select(AuditEventModel).where(AuditEventModel.incident_id == incident_id))).scalars().all()
    return [
        {
            "event_id": row.event_id,
            "occurred_at": row.occurred_at.isoformat(),
            "event_type": row.event_type,
            "action": row.action,
            "details": json.loads(row.details_json or "{}"),
            "source": row.source,
        }
        for row in rows
    ]


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    status: str = Query(...),
) -> FraudSpikeIncident:
    incidents = _detected_incidents()
    incident = next((item for item in incidents if item.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        incident.status = IncidentStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid incident status") from exc
    incident.updated_at = datetime.now(UTC)
    await _create_audit_record(
        incident_id=incident_id,
        action="status_updated",
        details={"status": incident.status.value},
    )
    return incident


@router.get("/incidents/{incident_id}/investigation")
async def incident_investigation(incident_id: str) -> Investigation:
    incidents = _detected_incidents()
    incident = next((item for item in incidents if item.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    investigation = build_investigation_for_incident(incident)
    async with session_factory() as session:
        await persist_investigation(session, investigation)
    return investigation


@router.get("/incidents/{incident_id}/verification")
async def incident_verification(incident_id: str) -> dict[str, object]:
    incidents = _detected_incidents()
    incident = next((item for item in incidents if item.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return verify_investigation_claims(
        incident,
        [
            "The merchant was flagged because its observed fraud rate exceeded baseline.",
            "The transaction volume and suspicious pattern supported the alert.",
            "The system evidence confirms the detection window.",
        ],
    )


@router.get("/demo/evaluation")
async def demo_evaluation() -> dict[str, object]:
    split = _dataset_key()
    dataset_events = split["train"] + split["validation"] + split["test"]
    incidents = detect_merchant_spikes(dataset_events)
    merchant_predictions = {incident.merchant_id: True for incident in incidents}
    actual: list[int] = []
    predicted: list[int] = []
    for event in split["test"]:
        merchant_id = event.merchant_id
        actual.append(1 if event.fraud_label is FraudLabel.FRAUDULENT else 0)
        predicted.append(1 if merchant_predictions.get(merchant_id, False) else 0)

    result = evaluate_held_out_predictions(
        actual,
        predicted,
        dataset_version="synthetic-demo-v1",
        held_out_test_set_id="test-period-v1",
        detector_version="merchant-fraud-spike-v1",
        false_positive_cost_per_case=Decimal("125.00"),
    )
    return {
        "test_set_size": result.test_set_size,
        "tp": result.true_positives,
        "tn": result.true_negatives,
        "fp": result.false_positives,
        "fn": result.false_negatives,
        "precision": str(result.precision),
        "recall": str(result.recall),
        "f1": str(result.f1),
        "confusion_matrix": result.confusion_matrix,
        "false_positive_cost": str(result.false_positive_cost),
    }


@router.get("/demo/razorpay")
async def razorpay_status() -> dict[str, str | bool]:
    status = get_razorpay_status()
    return {
        "enabled": status.enabled,
        "mode": status.mode,
        "message": status.message,
    }


@router.get("/demo/investigation")
async def demo_investigation() -> Investigation:
    incidents = _detected_incidents()
    if not incidents:
        raise HTTPException(status_code=404, detail="No incidents found in the demo dataset")
    return build_investigation_for_incident(incidents[0])
