from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from app.db.database import session_factory
from app.detectors.fraud_spike import detect_merchant_spikes
from app.models import FraudSpikeIncidentModel, PaymentEventModel
from app.schemas import (
    AuditEvent,
    AuditEventType,
    CoarseGeography,
    FraudLabel,
    FraudSpikeIncident,
    PaymentEvent,
    PaymentMethodType,
    PaymentStatus,
)
from app.services.risk_engine import analyze_batch, score_transaction
from app.services.storage import persist_audit_event, persist_incident, persist_payment_events


def _as_decimal(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("Amount must be a positive numeric value.")
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Amount must be a positive numeric value.") from exc
    if not decimal_value.is_finite():
        raise ValueError("Amount must be finite.")
    return decimal_value


def _normalize_event(raw: dict[str, Any]) -> PaymentEvent:
    if not isinstance(raw, dict):
        raise ValueError("Each row must be an object.")

    payload_size = len(json.dumps(raw, default=str))
    if payload_size > 32768:
        raise ValueError("Payload exceeds maximum allowed size.")

    required = ["event_id", "merchant_id", "occurred_at", "amount"]
    for key in required:
        if key not in raw or raw[key] in (None, ""):
            raise ValueError(f"Missing required field: {key}")

    event_id = str(raw["event_id"]).strip()
    merchant_id = str(raw["merchant_id"]).strip()
    if not event_id or not merchant_id:
        raise ValueError("event_id and merchant_id must be non-empty strings.")

    amount = _as_decimal(raw["amount"])
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    occurred_at = raw["occurred_at"]
    if isinstance(occurred_at, str):
        try:
            dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Malformed timestamp.") from exc
    else:
        try:
            dt = datetime.fromisoformat(str(occurred_at))
        except ValueError as exc:
            raise ValueError("Malformed timestamp.") from exc

    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timestamps must include timezone offset information.")
    dt = dt.astimezone(UTC)

    payment_method_raw = raw.get("payment_method", "card")
    try:
        method = PaymentMethodType(str(payment_method_raw).lower())
    except ValueError as exc:
        raise ValueError("Invalid payment method.") from exc

    payment_status_raw = raw.get("payment_status", "captured")
    try:
        payment_status = PaymentStatus(str(payment_status_raw).lower())
    except ValueError as exc:
        raise ValueError("Invalid transaction status.") from exc

    currency_raw = str(raw.get("currency", "INR")).upper()
    if len(currency_raw) != 3 or not currency_raw.isalpha():
        raise ValueError("Currency must be a valid 3-letter ISO code.")

    geography = raw.get("geography")
    geog = None
    if geography is not None:
        if not isinstance(geography, dict):
            raise ValueError("Geography must be an object when provided.")
        country_code = geography.get("country_code")
        region_code = geography.get("region_code")
        if country_code is not None:
            country_code = str(country_code).upper()
        if region_code is not None:
            region_code = str(region_code)
        geog = CoarseGeography(country_code=country_code, region_code=region_code)

    fraud_label_value = raw.get("fraud_label")
    if fraud_label_value in (None, ""):
        fraud_label = FraudLabel.UNKNOWN
    else:
        try:
            fraud_label = FraudLabel(str(fraud_label_value).lower())
        except ValueError as exc:
            raise ValueError("Invalid fraud label.") from exc

    metadata = raw.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("Metadata must be an object when provided.")
    if metadata is None:
        metadata = {}
    if len(json.dumps(metadata, default=str)) > 8192:
        raise ValueError("Metadata exceeds the per-event size limit.")

    customer_reference = raw.get("customer_reference")
    device_reference = raw.get("device_reference")

    return PaymentEvent(
        event_id=event_id,
        merchant_id=merchant_id,
        occurred_at=dt,
        amount=amount.quantize(Decimal("0.01")),
        currency=currency_raw,
        payment_method=method,
        payment_status=payment_status,
        customer_reference=str(customer_reference or f"customer-{merchant_id}"),
        device_reference=str(device_reference or f"device-{event_id}"),
        geography=geog,
        fraud_label=fraud_label,
        metadata=metadata,
    )


async def _load_merchant_history(session, merchant_id: str, before: datetime | None = None) -> list[PaymentEvent]:
    stmt = select(PaymentEventModel).where(PaymentEventModel.merchant_id == merchant_id)
    if before is not None:
        stmt = stmt.where(PaymentEventModel.occurred_at < before)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        PaymentEvent(
            event_id=row.event_id,
            merchant_id=row.merchant_id,
            occurred_at=row.occurred_at,
            amount=row.amount,
            currency=row.currency,
            payment_method=PaymentMethodType(row.payment_method),
            payment_status=PaymentStatus(row.payment_status),
            customer_reference=row.customer_reference,
            device_reference=row.device_reference,
            geography=(
                None
                if row.geography_country is None and row.geography_region is None
                else {"country_code": row.geography_country, "region_code": row.geography_region}
            ),
            fraud_label=FraudLabel(row.fraud_label),
            metadata=json.loads(row.metadata_json or "{}"),
        )
        for row in rows
    ]


async def _create_incidents_for_inserted_events(session, accepted_events: list[PaymentEvent]) -> list[str]:
    if not accepted_events:
        return []
    all_events = []
    for event in accepted_events:
        historical = await _load_merchant_history(session, event.merchant_id)
        all_events.extend(historical)
    all_events.extend(accepted_events)
    incidents = detect_merchant_spikes(all_events)
    incident_ids: list[str] = []
    for incident in incidents:
        existing = await session.execute(
            select(FraudSpikeIncidentModel).where(FraudSpikeIncidentModel.incident_id == incident.incident_id)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        incident.created_at = incident.detected_at
        incident.updated_at = incident.detected_at
        await persist_incident(session, incident)
        incident_ids.append(incident.incident_id)
        await persist_audit_event(
            session,
            AuditEvent(
                event_id=f"audit-incident-{incident.incident_id}",
                occurred_at=datetime.now(UTC),
                event_type=AuditEventType.DETECTION,
                actor="system",
                source="ingestion",
                incident_id=incident.incident_id,
                action="merchant_spike_detected",
                details={
                    "merchant_id": incident.merchant_id,
                    "severity": incident.severity.value,
                    "observed_fraud_rate": str(incident.observed_fraud_rate),
                    "baseline_fraud_rate": str(incident.baseline_fraud_rate),
                },
            ),
        )
    return incident_ids


async def validate_and_ingest_events(raw_events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted: list[PaymentEvent] = []
    rejected: list[dict[str, Any]] = []
    duplicates: list[str] = []
    incidents_created: list[str] = []

    if not raw_events:
        return {
            "accepted": 0,
            "rejected": 0,
            "duplicate/skipped": 0,
            "incidents_created": 0,
            "records_received": 0,
            "records_accepted": 0,
            "records_rejected": 0,
            "duplicates": 0,
            "risk_summary": {"records_processed": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0, "fraud_rate": 0.0, "average_risk": 0.0, "merchants_affected": 0, "top_risk_merchants": []},
            "rejected_rows": [],
            "processing_time_ms": 0,
        }

    async with session_factory() as session:
        for index, raw in enumerate(raw_events):
            try:
                event = _normalize_event(raw)
                existing = await session.execute(
                    select(PaymentEventModel).where(PaymentEventModel.event_id == event.event_id)
                )
                if existing.scalar_one_or_none() is not None:
                    duplicates.append(event.event_id)
                    continue
                accepted.append(event)
            except Exception as exc:
                rejected.append({"index": index, "error": "Invalid event payload.", "payload": raw})

        if accepted:
            await persist_payment_events(session, accepted)
            for event in accepted:
                history = await _load_merchant_history(session, event.merchant_id, event.occurred_at)
                risk = score_transaction(event, history)
                await persist_audit_event(
                    session,
                    AuditEvent(
                        event_id=f"audit-ingest-{event.event_id}",
                        occurred_at=datetime.now(UTC),
                        event_type=AuditEventType.DATA_ACCESS,
                        actor="system",
                        source="ingestion",
                        action="EVENT_INGESTED",
                        details={
                            "merchant_id": event.merchant_id,
                            "event_id": event.event_id,
                            "risk_score": risk["risk_score"],
                            "decision": risk["decision"],
                        },
                    ),
                )
            incidents_created = await _create_incidents_for_inserted_events(session, accepted)
            summary = {
                "accepted": len(accepted),
                "rejected": len(rejected),
                "duplicate/skipped": len(duplicates),
                "incidents_created": len(incidents_created),
                "records_received": len(raw_events),
                "records_accepted": len(accepted),
                "records_rejected": len(rejected),
                "duplicates": len(duplicates),
                "merchants_detected": len({item.merchant_id for item in accepted}),
                "processing_time_ms": 0,
                "risk_summary": analyze_batch(accepted),
                "rejected_rows": rejected,
            }
            return summary

        summary = {
            "accepted": 0,
            "rejected": len(rejected),
            "duplicate/skipped": len(duplicates),
            "incidents_created": 0,
            "records_received": len(raw_events),
            "records_accepted": 0,
            "records_rejected": len(rejected),
            "duplicates": len(duplicates),
            "merchants_detected": 0,
            "processing_time_ms": 0,
            "risk_summary": {"records_processed": 0, "high_risk": 0, "medium_risk": 0, "low_risk": 0, "fraud_rate": 0.0, "average_risk": 0.0, "merchants_affected": 0, "top_risk_merchants": []},
            "rejected_rows": rejected,
        }
        return summary


def build_synthetic_stream(scenario: str = "FRAUD SPIKE") -> list[dict[str, Any]]:
    merchants = [
        ("merchant-002", 1100, 0.28, "KA"),
        ("merchant-005", 3600, 0.41, "MH"),
        ("merchant-003", 760, 0.07, "MH"),
        ("merchant-001", 430, 0.02, "KA"),
        ("merchant-006", 620, 0.04, "TN"),
    ]
    events: list[dict[str, Any]] = []
    for index in range(12):
        merchant_id, base_amount, merchant_rate, region = merchants[index % len(merchants)]
        amount = base_amount * (1.2 + (index % 5) * 0.8)
        if scenario == "HIGH VELOCITY":
            amount = base_amount * 4.5
        elif scenario == "COLD START":
            merchant_id = "merchant-new"
            amount = 2100 + (index * 180)
        elif scenario == "FALSE POSITIVE / BORDERLINE":
            amount = base_amount * 1.5
        event = {
            "event_id": f"demo-{scenario.lower().replace(' ', '-')}-{index}",
            "merchant_id": merchant_id,
            "occurred_at": datetime.now(UTC).isoformat(),
            "amount": str(round(float(amount), 2)),
            "currency": "INR",
            "payment_method": "card" if index % 2 else "upi",
            "payment_status": "captured",
            "customer_reference": f"customer-{index + 50}",
            "device_reference": f"device-{index + 200}",
            "geography": {"country_code": "IN", "region_code": region},
            "fraud_label": "unknown",
            "metadata": {
                "velocity_1h": 2 + (index % 4),
                "velocity_24h": 6 + (index % 7),
                "baseline_amount": str(base_amount),
                "current_amount": str(amount),
                "current_fraud_rate": str(merchant_rate),
                "previous_fraud_rate": str(max(merchant_rate * 0.25, 0.02)),
                "historical_transaction_count": 12,
                "historical_fraud_count": 2,
            },
        }
        events.append(event)
    return events
