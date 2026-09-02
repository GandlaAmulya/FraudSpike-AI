from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.api.routes import api_router
from app.core.config import settings
from app.db.database import engine, session_factory
from app.detectors.fraud_spike import detect_merchant_spikes
from app.models import AuditEventModel, PaymentEventModel
from app.models.base import Base
from app.schemas import AuditEvent, AuditEventType
from app.services.dataset import build_demo_dataset
from app.services.investigation import build_investigation_for_incident
from app.services.storage import persist_audit_event, persist_incident, persist_investigation, persist_payment_events

app = FastAPI(
    title="FraudSpike AI API",
    version="0.1.0",
    description="Defensive payment fraud-spike detection service foundation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _seed_demo_environment() -> None:
    """Populate the local SQLite database with a deterministic demo workflow when it is incomplete."""
    async with session_factory() as session:
        payment_count = await session.scalar(select(func.count()).select_from(PaymentEventModel))
        incident_count = await session.scalar(select(func.count()).select_from(__import__('app.models', fromlist=['FraudSpikeIncidentModel']).FraudSpikeIncidentModel))
        investigation_count = await session.scalar(select(func.count()).select_from(__import__('app.models', fromlist=['InvestigationModel']).InvestigationModel))
        audit_count = await session.scalar(select(func.count()).select_from(__import__('app.models', fromlist=['AuditEventModel']).AuditEventModel))

        if payment_count and payment_count > 0 and incident_count and incident_count > 0 and investigation_count and investigation_count > 0 and audit_count and audit_count > 0:
            return

        events = build_demo_dataset()
        if not payment_count or payment_count == 0:
            await persist_payment_events(session, events)

        incidents = detect_merchant_spikes(events)
        for incident in incidents[:3]:
            merchant_events = [event for event in events if event.merchant_id == incident.merchant_id]
            investigation = build_investigation_for_incident(incident, merchant_events=merchant_events)

            existing_incident = await session.execute(
                select(__import__('app.models', fromlist=['FraudSpikeIncidentModel']).FraudSpikeIncidentModel).where(
                    __import__('app.models', fromlist=['FraudSpikeIncidentModel']).FraudSpikeIncidentModel.incident_id == incident.incident_id
                )
            )
            if existing_incident.scalar_one_or_none() is None:
                await persist_incident(session, incident)

            existing_investigation = await session.execute(
                select(__import__('app.models', fromlist=['InvestigationModel']).InvestigationModel).where(
                    __import__('app.models', fromlist=['InvestigationModel']).InvestigationModel.investigation_id == investigation.investigation_id
                )
            )
            if existing_investigation.scalar_one_or_none() is None:
                await persist_investigation(session, investigation)

            existing_audit = await session.execute(
                select(__import__('app.models', fromlist=['AuditEventModel']).AuditEventModel).where(
                    __import__('app.models', fromlist=['AuditEventModel']).AuditEventModel.event_id == f"demo-audit-{incident.incident_id}-detection"
                )
            )
            if existing_audit.scalar_one_or_none() is None:
                await persist_audit_event(
                    session,
                    AuditEvent(
                        event_id=f"demo-audit-{incident.incident_id}-detection",
                        occurred_at=datetime.now(UTC),
                        event_type=AuditEventType.DETECTION,
                        source="demo-seed",
                        incident_id=incident.incident_id,
                        investigation_id=investigation.investigation_id,
                        action="demo_seed",
                        details={
                            "merchant_id": incident.merchant_id,
                            "severity": incident.severity.value,
                            "status": incident.status.value,
                            "observed_fraud_rate": str(incident.observed_fraud_rate),
                        },
                    ),
                )

            existing_audit_investigation = await session.execute(
                select(__import__('app.models', fromlist=['AuditEventModel']).AuditEventModel).where(
                    __import__('app.models', fromlist=['AuditEventModel']).AuditEventModel.event_id == f"demo-audit-{incident.incident_id}-investigation"
                )
            )
            if existing_audit_investigation.scalar_one_or_none() is None:
                await persist_audit_event(
                    session,
                    AuditEvent(
                        event_id=f"demo-audit-{incident.incident_id}-investigation",
                        occurred_at=datetime.now(UTC),
                        event_type=AuditEventType.INVESTIGATION,
                        source="demo-seed",
                        incident_id=incident.incident_id,
                        investigation_id=investigation.investigation_id,
                        action="investigation_generated",
                        details={
                            "merchant_id": incident.merchant_id,
                            "risk_level": investigation.risk_level,
                            "ml_available": bool(investigation.ml_assessment and investigation.ml_assessment.get("available")),
                        },
                    ),
                )


@app.on_event("startup")
async def startup() -> None:
    """Initialize the local SQLite schema and seed deterministic demo data."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await _seed_demo_environment()


app.include_router(api_router)


@app.get("/api/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return service availability without touching product data."""
    return {"status": "ok", "service": "fraudspike-backend"}