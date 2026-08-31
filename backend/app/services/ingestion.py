from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.db.database import session_factory
from app.schemas import (
    CoarseGeography,
    FraudLabel,
    PaymentEvent,
    PaymentMethodType,
    PaymentStatus,
)
from app.services.risk_engine import analyze_batch, score_transaction
from app.services.storage import persist_audit_event, persist_payment_events
from app.models import AuditEventModel
from app.schemas import AuditEvent, AuditEventType


def _as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _normalize_event(raw: dict[str, Any]) -> PaymentEvent:
    if not isinstance(raw, dict):
        raise ValueError("Each row must be an object.")
    required = [
        "event_id",
        "merchant_id",
        "occurred_at",
        "amount",
    ]
    for key in required:
        if key not in raw or raw[key] in (None, ""):
            raise ValueError(f"Missing required field: {key}")

    amount = _as_decimal(raw["amount"])
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    occurred_at = raw["occurred_at"]
    if isinstance(occurred_at, str):
        dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(str(occurred_at))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)

    payment_method = raw.get("payment_method", "card")
    try:
        method = PaymentMethodType(payment_method)
    except ValueError:
        method = PaymentMethodType.CARD

    status = raw.get("payment_status", "captured")
    try:
        payment_status = PaymentStatus(status)
    except ValueError:
        payment_status = PaymentStatus.CAPTURED

    geography = raw.get("geography")
    geog = None
    if isinstance(geography, dict):
        geog = CoarseGeography(
            country_code=geography.get("country_code", "IN"),
            region_code=geography.get("region_code", "KA"),
        )

    return PaymentEvent(
        event_id=str(raw["event_id"]),
        merchant_id=str(raw["merchant_id"]),
        occurred_at=dt,
        amount=amount,
        currency=str(raw.get("currency", "INR")).upper(),
        payment_method=method,
        payment_status=payment_status,
        customer_reference=str(raw.get("customer_reference", f"customer-{raw['merchant_id']}")),
        device_reference=str(raw.get("device_reference", f"device-{raw['event_id']}")),
        geography=geog,
        fraud_label=FraudLabel(raw.get("fraud_label", "unknown")) if raw.get("fraud_label") else FraudLabel.UNKNOWN,
        metadata={
            **(raw.get("metadata") or {}),
            "historic_transaction_count": int(raw.get("historical_transaction_count", 0) or 0),
            "historical_fraud_count": int(raw.get("historical_fraud_count", 0) or 0),
            "velocity_1h": int(raw.get("velocity_1h", 0) or 0),
            "velocity_24h": int(raw.get("velocity_24h", 0) or 0),
            "baseline_amount": _as_decimal(raw.get("baseline_amount", amount)),
            "current_amount": amount,
            "current_fraud_rate": _as_decimal(raw.get("current_fraud_rate", "0.03")),
            "previous_fraud_rate": _as_decimal(raw.get("previous_fraud_rate", "0.02")),
        },
    )


async def validate_and_ingest_events(raw_events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted: list[PaymentEvent] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(raw_events):
        try:
            event = _normalize_event(raw)
            if event.event_id in seen_ids:
                raise ValueError("Duplicate transaction ID")
            accepted.append(event)
            seen_ids.add(event.event_id)
        except Exception as exc:  # pragma: no cover - validated at API boundary
            rejected.append({"index": index, "error": str(exc), "payload": raw})

    summary = {"records_received": len(raw_events), "records_accepted": len(accepted), "records_rejected": len(rejected), "merchants_detected": len({item.merchant_id for item in accepted})}
    if accepted:
        async with session_factory() as session:
            await persist_payment_events(session, accepted)
            for event in accepted:
                risk = score_transaction(event, [item for item in accepted if item.merchant_id == event.merchant_id and item.occurred_at < event.occurred_at])
                audit_event = AuditEvent(
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
                )
                await persist_audit_event(session, audit_event)

    summary["processing_time_ms"] = 0
    summary["risk_summary"] = analyze_batch(accepted)
    summary["rejected_rows"] = rejected
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
