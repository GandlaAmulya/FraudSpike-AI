from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PaymentEventModel(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    merchant_id: Mapped[str] = mapped_column(String(128), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    payment_method: Mapped[str] = mapped_column(String(32))
    payment_status: Mapped[str] = mapped_column(String(32))
    customer_reference: Mapped[str] = mapped_column(String(128))
    device_reference: Mapped[str] = mapped_column(String(128))
    geography_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    geography_region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fraud_label: Mapped[str] = mapped_column(String(32), default="unknown")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class FraudSpikeIncidentModel(Base):
    __tablename__ = "fraud_spike_incidents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    incident_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    merchant_id: Mapped[str] = mapped_column(String(128), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    analysis_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    analysis_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    baseline_fraud_rate: Mapped[Decimal] = mapped_column(DECIMAL(8, 6))
    observed_fraud_rate: Mapped[Decimal] = mapped_column(DECIMAL(8, 6))
    deviation: Mapped[Decimal] = mapped_column(DECIMAL(12, 6))
    affected_transaction_count: Mapped[int] = mapped_column(default=0)
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="detected")
    detector_version: Mapped[str] = mapped_column(String(128))
    confidence: Mapped[Decimal | None] = mapped_column(DECIMAL(8, 6), nullable=True)
    risk_score: Mapped[Decimal | None] = mapped_column(DECIMAL(8, 6), nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    suspicious_event_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    investigation_notes_json: Mapped[str] = mapped_column(Text, default="[]")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InvestigationModel(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    investigation_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    incident_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hypotheses_json: Mapped[str] = mapped_column(Text, default="[]")
    evidence_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    verification_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(DECIMAL(8, 6), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    findings_json: Mapped[str] = mapped_column(Text, default="[]")
    evidence_references_json: Mapped[str] = mapped_column(Text, default="[]")
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ml_assessment_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations_json: Mapped[str] = mapped_column(Text, default="[]")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    investigation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
