from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditEventModel,
    FraudSpikeIncidentModel,
    InvestigationModel,
    PaymentEventModel,
)
from app.schemas import (
    AuditEvent,
    AuditEventType,
    FraudSpikeIncident,
    IncidentStatus,
    Investigation,
    PaymentEvent,
)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def persist_payment_events(session: AsyncSession, events: list[PaymentEvent]) -> None:
    for event in events:
        row = await session.get(PaymentEventModel, event.event_id) if False else None
        existing = await session.execute(
            select(PaymentEventModel).where(PaymentEventModel.event_id == event.event_id)
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row is not None:
            continue

        session.add(
            PaymentEventModel(
                event_id=event.event_id,
                merchant_id=event.merchant_id,
                occurred_at=event.occurred_at,
                amount=event.amount,
                currency=event.currency,
                payment_method=event.payment_method.value,
                payment_status=event.payment_status.value,
                customer_reference=event.customer_reference,
                device_reference=event.device_reference,
                geography_country=(event.geography.country_code if event.geography else None),
                geography_region=(event.geography.region_code if event.geography else None),
                fraud_label=event.fraud_label.value,
                metadata_json=json.dumps(event.metadata),
            )
        )
    await session.commit()


def _incident_status_from_row(row: FraudSpikeIncidentModel) -> FraudSpikeIncident:
    return FraudSpikeIncident(
        incident_id=row.incident_id,
        merchant_id=row.merchant_id,
        detected_at=_as_utc(row.detected_at),
        analysis_window={
            "start_at": _as_utc(row.analysis_window_start),
            "end_at": _as_utc(row.analysis_window_end),
        },
        baseline_fraud_rate=row.baseline_fraud_rate,
        observed_fraud_rate=row.observed_fraud_rate,
        deviation=row.deviation,
        affected_transaction_count=row.affected_transaction_count,
        severity=row.severity,
        status=row.status,
        detector_version=row.detector_version,
        confidence=row.confidence,
        risk_score=row.risk_score,
        evidence=[
            item
            for item in json.loads(row.evidence_json or "[]")
        ],
        suspicious_event_ids=json.loads(row.suspicious_event_ids_json or "[]"),
        investigation_notes=json.loads(row.investigation_notes_json or "[]"),
        resolution=row.resolution,
        created_at=_as_utc(row.created_at),
        updated_at=_as_utc(row.updated_at),
    )


async def get_incident_by_id(session: AsyncSession, incident_id: str) -> FraudSpikeIncident | None:
    existing = await session.execute(
        select(FraudSpikeIncidentModel).where(FraudSpikeIncidentModel.incident_id == incident_id)
    )
    row = existing.scalar_one_or_none()
    if row is None:
        return None
    return _incident_status_from_row(row)


async def persist_incident(session: AsyncSession, incident: FraudSpikeIncident) -> None:
    existing = await session.execute(
        select(FraudSpikeIncidentModel).where(FraudSpikeIncidentModel.incident_id == incident.incident_id)
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = FraudSpikeIncidentModel(incident_id=incident.incident_id)
        session.add(row)

    row.merchant_id = incident.merchant_id
    row.detected_at = incident.detected_at
    row.analysis_window_start = incident.analysis_window.start_at
    row.analysis_window_end = incident.analysis_window.end_at
    row.baseline_fraud_rate = incident.baseline_fraud_rate
    row.observed_fraud_rate = incident.observed_fraud_rate
    row.deviation = incident.deviation
    row.affected_transaction_count = incident.affected_transaction_count
    row.severity = incident.severity.value
    row.status = incident.status.value
    row.detector_version = incident.detector_version
    row.confidence = incident.confidence
    row.risk_score = incident.risk_score
    row.evidence_json = json.dumps([item.model_dump(mode="json") for item in incident.evidence])
    row.suspicious_event_ids_json = json.dumps(incident.suspicious_event_ids)
    row.investigation_notes_json = json.dumps(incident.investigation_notes)
    row.resolution = incident.resolution
    row.version = (row.version or 0) + 1
    row.created_at = incident.created_at or incident.detected_at
    row.updated_at = incident.updated_at or incident.detected_at
    await session.commit()


VALID_INCIDENT_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.DETECTED: {
        IncidentStatus.INVESTIGATING,
        IncidentStatus.VERIFIED,
        IncidentStatus.DISMISSED,
    },
    IncidentStatus.INVESTIGATING: {
        IncidentStatus.VERIFIED,
        IncidentStatus.DISMISSED,
        IncidentStatus.RESOLVED,
    },
    IncidentStatus.VERIFIED: {
        IncidentStatus.RESOLVED,
    },
    IncidentStatus.DISMISSED: set(),
    IncidentStatus.RESOLVED: set(),
}


INCIDENT_ACTION_STATUS_MAP: dict[str, IncidentStatus] = {
    "confirm": IncidentStatus.VERIFIED,
    "verify": IncidentStatus.VERIFIED,
    "dismiss": IncidentStatus.DISMISSED,
    "resolve": IncidentStatus.RESOLVED,
    "investigate": IncidentStatus.INVESTIGATING,
    "investigating": IncidentStatus.INVESTIGATING,
}


async def transition_incident_status(
    session: AsyncSession,
    *,
    incident_id: str,
    action: str,
    actor: str = "analyst",
    reason: str | None = None,
) -> FraudSpikeIncident:
    row = await session.execute(
        select(FraudSpikeIncidentModel).where(FraudSpikeIncidentModel.incident_id == incident_id)
    )
    current_row = row.scalar_one_or_none()
    if current_row is None:
        raise ValueError("Incident not found")

    current_status = IncidentStatus(current_row.status)
    target_status = INCIDENT_ACTION_STATUS_MAP.get(action.lower())
    if target_status is None:
        raise ValueError(f"Unsupported incident action: {action}")

    if current_status == target_status:
        current_row.updated_at = datetime.now(UTC)
        current_row.version = (current_row.version or 0) + 1
        return _incident_status_from_row(current_row)

    allowed = VALID_INCIDENT_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ValueError(
            f"Invalid incident transition: {current_status.value} -> {target_status.value}"
        )

    previous_status = current_status
    current_row.status = target_status.value
    current_row.updated_at = datetime.now(UTC)
    current_row.version = (current_row.version or 0) + 1
    incident = _incident_status_from_row(current_row)
    incident.created_at = _as_utc(current_row.created_at) or _as_utc(current_row.detected_at)
    incident.updated_at = _as_utc(current_row.updated_at) or _as_utc(current_row.detected_at)

    await persist_audit_event(
        session,
        AuditEvent(
            event_id=f"audit-{incident_id}-{action.lower()}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}",
            occurred_at=datetime.now(UTC),
            event_type=AuditEventType.RESPONSE,
            actor=actor,
            incident_id=incident_id,
            action=action.lower(),
            details={
                "merchant_id": current_row.merchant_id,
                "previous_status": previous_status.value,
                "new_status": target_status.value,
                "action": action.lower(),
                "actor": actor,
                "reason": reason or "",
            },
        ),
    )
    await session.commit()
    return incident


async def persist_investigation(session: AsyncSession, investigation: Investigation) -> None:
    existing = await session.execute(
        select(InvestigationModel).where(InvestigationModel.investigation_id == investigation.investigation_id)
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = InvestigationModel(investigation_id=investigation.investigation_id)
        session.add(row)

    row.incident_id = investigation.incident_id
    row.status = investigation.status.value
    row.started_at = investigation.started_at
    row.ended_at = investigation.ended_at
    row.hypotheses_json = json.dumps(investigation.hypotheses)
    row.evidence_ids_json = json.dumps(investigation.evidence_ids)
    row.verification_result = investigation.verification_result.value if investigation.verification_result else None
    row.confidence = investigation.confidence
    row.explanation = investigation.explanation
    row.recommended_response = investigation.recommended_defensive_response
    row.assessment = investigation.assessment
    row.risk_level = investigation.risk_level
    row.findings_json = json.dumps(investigation.findings)
    row.evidence_references_json = json.dumps(investigation.evidence_references)
    row.reasoning_summary = investigation.reasoning_summary
    row.recommended_action = investigation.recommended_action
    row.limitations_json = json.dumps(investigation.limitations)
    row.generated_at = investigation.generated_at
    await session.commit()


async def persist_audit_event(session: AsyncSession, event: AuditEvent) -> None:
    session.add(
        AuditEventModel(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            event_type=event.event_type.value,
            actor=event.actor,
            source=event.source,
            incident_id=event.incident_id,
            investigation_id=event.investigation_id,
            action=event.action,
            details_json=json.dumps(event.details),
        )
    )
    await session.commit()


async def get_dashboard_summary(session: AsyncSession) -> dict[str, object]:
    total_tx = await session.scalar(select(func.count()).select_from(PaymentEventModel))
    fraud_rows = await session.execute(
        select(PaymentEventModel).where(PaymentEventModel.fraud_label == "fraudulent")
    )
    fraud_count = len(fraud_rows.scalars().all())
    cost = Decimal(fraud_count) * Decimal("125.00")

    incident_rows = await session.execute(select(FraudSpikeIncidentModel))
    incidents = incident_rows.scalars().all()
    severity_breakdown = {
        "critical": sum(1 for item in incidents if item.severity == "critical"),
        "high": sum(1 for item in incidents if item.severity == "high"),
        "medium": sum(1 for item in incidents if item.severity == "medium"),
        "low": sum(1 for item in incidents if item.severity == "low"),
    }

    merchant_query = await session.execute(
        select(PaymentEventModel.merchant_id, func.count(PaymentEventModel.id), func.sum(PaymentEventModel.fraud_label == "fraudulent"))
    )
    merchant_rows = merchant_query.all()
    merchant_risk = [
        {
            "merchant_id": merchant_id,
            "total_transactions": total,
            "fraudulent_transactions": int(fraud_total or 0),
            "fraud_rate": round((int(fraud_total or 0) / total) if total else 0, 4),
        }
        for merchant_id, total, fraud_total in merchant_rows
    ]
    merchant_risk.sort(key=lambda item: item["fraud_rate"], reverse=True)

    return {
        "total_transactions": int(total_tx or 0),
        "fraud_rate": round((fraud_count / total_tx) if total_tx else 0, 4),
        "active_incidents": len(incidents),
        "severity_breakdown": severity_breakdown,
        "merchant_risk_ranking": merchant_risk[:5],
        "false_positive_cost_estimate": str(cost.quantize(Decimal("0.01"))),
    }


async def list_incidents(session: AsyncSession) -> list[FraudSpikeIncident]:
    rows = (await session.execute(select(FraudSpikeIncidentModel))).scalars().all()
    return [_incident_status_from_row(row) for row in rows]
