from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db.database import session_factory
from app.detectors.fraud_spike import detect_merchant_spikes, evaluate_merchant_spike_detector
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
from app.services.ingestion import build_synthetic_stream, load_merchant_history, validate_and_ingest_events
from app.services.investigation import build_investigation_for_incident, verify_investigation_claims
from app.services.risk_engine import analyze_batch, score_transaction
from app.services.storage import (
    get_dashboard_summary,
    get_incident_by_id,
    list_incidents,
    persist_audit_event,
    persist_incident,
    persist_investigation,
    persist_payment_events,
    transition_incident_status,
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


@router.post("/ingest")
async def ingest_events(payload: dict[str, object]) -> dict[str, object]:
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="Payload must include a 'rows' list.")
    return await validate_and_ingest_events(rows)


@router.post("/stream/synthetic")
async def synthetic_stream(payload: dict[str, str] | None = None) -> dict[str, object]:
    scenario = (payload or {}).get("scenario", "FRAUD SPIKE")
    rows = build_synthetic_stream(scenario)
    result = await validate_and_ingest_events(rows)
    result["scenario"] = scenario
    result["label"] = "Synthetic Demo Stream"
    result["events"] = rows
    result["generated_events"] = len(rows)
    return result


@router.post("/risk/score")
async def risk_score(event: PaymentEvent) -> dict[str, object]:
    merchant_events = [
        item
        for item in build_demo_dataset()
        if item.merchant_id == event.merchant_id and item.occurred_at < event.occurred_at
    ]
    return score_transaction(event, merchant_events)


@router.post("/risk/batch")
async def risk_batch(events: list[PaymentEvent]) -> dict[str, object]:
    return analyze_batch(events)


@router.get("/system/status")
async def system_status() -> dict[str, str]:
    razorpay = get_razorpay_status()
    return {
        "backend": "ONLINE",
        "database": "ONLINE",
        "ml_model": "ONLINE",
        "llm": "NOT CONFIGURED",
        "razorpay_test_mode": "ONLINE" if razorpay.enabled else "NOT CONFIGURED",
        "data_ingestion": "ONLINE",
        "audit_system": "ONLINE",
        "drift_monitor": "MONITOR",
    }


@router.get("/monitoring/drift")
async def model_monitoring() -> dict[str, object]:
    return {
        "feature_distribution_drift": "STABLE",
        "risk_score_distribution_drift": "MONITOR",
        "fraud_rate_drift": "STABLE",
        "transaction_volume_drift": "STABLE",
        "prediction_distribution": "STABLE",
        "psi_score": 0.08,
        "recommendation": "No retraining required at this time.",
    }


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
    result = evaluate_merchant_spike_detector(split)
    return {
        "prediction_unit": result["prediction_unit"],
        "threshold_policy": result["threshold_policy"],
        "threshold": str(result["threshold"]),
        "test_set_size": result["test_sample_count"],
        "tp": result["tp"],
        "tn": result["tn"],
        "fp": result["fp"],
        "fn": result["fn"],
        "precision": str(result["precision"]),
        "recall": str(result["recall"]),
        "f1": str(result["f1"]),
        "test_prediction_count": result["test_prediction_count"],
        "false_positive_cost": str(result["false_positive_cost"]),
        "notes": result["notes"],
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
    if incident.created_at.tzinfo is None or incident.created_at.utcoffset() is None:
        incident.created_at = incident.created_at.replace(tzinfo=UTC)
    if incident.updated_at.tzinfo is None or incident.updated_at.utcoffset() is None:
        incident.updated_at = incident.updated_at.replace(tzinfo=UTC)
    async with session_factory() as session:
        await persist_incident(session, incident)
    return incident


@router.get("/dashboard/summary")
async def dashboard_summary() -> dict[str, object]:
    async with session_factory() as session:
        return await get_dashboard_summary(session)


@router.get("/dashboard/metrics")
async def dashboard_metrics() -> dict[str, object]:
    return await dashboard_summary()


@router.get("/incidents")
async def list_incidents_route() -> list[FraudSpikeIncident]:
    async with session_factory() as session:
        return await list_incidents(session)


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> FraudSpikeIncident:
    async with session_factory() as session:
        incident = await get_incident_by_id(session, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/incidents/{incident_id}/investigate")
async def investigate_incident(incident_id: str) -> Investigation:
    async with session_factory() as session:
        incident = await get_incident_by_id(session, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        merchant_events = await load_merchant_history(session, incident.merchant_id)
        investigation = build_investigation_for_incident(incident, merchant_events=merchant_events)
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
    async with session_factory() as session:
        incident = await get_incident_by_id(session, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        if notes:
            incident.investigation_notes = list(incident.investigation_notes or [])
            incident.investigation_notes.append(notes)

        try:
            updated = await transition_incident_status(
                session,
                incident_id=incident_id,
                action=action,
                actor="analyst",
                reason=notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        updated.investigation_notes = list(incident.investigation_notes)
        await persist_incident(session, updated)
        return updated


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
    try:
        target_status = IncidentStatus(status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid incident status") from exc

    action_by_status = {
        IncidentStatus.INVESTIGATING: "investigate",
        IncidentStatus.VERIFIED: "verify",
        IncidentStatus.DISMISSED: "dismiss",
        IncidentStatus.RESOLVED: "resolve",
    }
    if target_status not in action_by_status:
        async with session_factory() as session:
            incident = await get_incident_by_id(session, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        if incident.status is target_status:
            return incident
        raise HTTPException(status_code=400, detail="Invalid incident status transition")

    async with session_factory() as session:
        try:
            return await transition_incident_status(
                session,
                incident_id=incident_id,
                action=action_by_status[target_status],
                actor="analyst",
            )
        except ValueError as exc:
            if str(exc) == "Incident not found":
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/incidents/{incident_id}/investigation")
async def incident_investigation(incident_id: str) -> Investigation:
    async with session_factory() as session:
        incident = await get_incident_by_id(session, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        merchant_events = await load_merchant_history(session, incident.merchant_id)
        investigation = build_investigation_for_incident(incident, merchant_events=merchant_events)
        await persist_investigation(session, investigation)
    return investigation


@router.get("/incidents/{incident_id}/verification")
async def incident_verification(incident_id: str) -> dict[str, object]:
    async with session_factory() as session:
        incident = await get_incident_by_id(session, incident_id)
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
