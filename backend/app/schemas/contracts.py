"""Strongly typed domain contracts shared by future API and service layers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, TypeAlias

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

Identifier = Annotated[str, Field(min_length=1, max_length=128)]
CurrencyCode = Annotated[
    str,
    Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"),
]
Money = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=2),
]
NonNegativeMoney = Annotated[
    Decimal,
    Field(ge=0, max_digits=18, decimal_places=2),
]
Probability = Annotated[Decimal, Field(ge=0, le=1, max_digits=8, decimal_places=6)]
JsonPrimitive: TypeAlias = str | int | float | bool | Decimal | None
JsonValue: TypeAlias = (
    JsonPrimitive | list[Any] | dict[str, Any]
)


def _as_utc(value: datetime) -> datetime:
    """Require aware timestamps and normalize them to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_as_utc)]


class ContractModel(BaseModel):
    """Base configuration shared by all domain contracts."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class FraudLabel(StrEnum):
    LEGITIMATE = "legitimate"
    FRAUDULENT = "fraudulent"
    UNKNOWN = "unknown"


class PaymentMethodType(StrEnum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"
    UPI = "upi"
    CASH = "cash"
    OTHER = "other"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    VERIFIED = "verified"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class EvidenceCategory(StrEnum):
    MERCHANT_BASELINE = "merchant_baseline"
    TRANSACTION_PATTERN = "transaction_pattern"
    TEMPORAL = "temporal"
    PAYMENT_METHOD = "payment_method"
    GEOGRAPHY = "geography"
    DEVICE = "device"
    CUSTOMER_PATTERN = "customer_pattern"
    EXTERNAL_SIGNAL = "external_signal"
    OTHER = "other"


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerificationResult(StrEnum):
    UNVERIFIED = "unverified"
    CONFIRMED_FRAUD_SPIKE = "confirmed_fraud_spike"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"


class AuditEventType(StrEnum):
    DETECTION = "detection"
    INVESTIGATION = "investigation"
    VERIFICATION = "verification"
    RESPONSE = "response"
    DATA_ACCESS = "data_access"
    SYSTEM = "system"


class CoarseGeography(ContractModel):
    """Coarse geography only; never store precise coordinates or addresses."""

    country_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="ISO 3166-1 alpha-2 country code.",
    )
    region_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=32,
        description="Coarse region/state/province code; not a street address.",
    )


class AnalysisWindow(ContractModel):
    """Inclusive/exclusive time range used by detection and evidence."""

    start_at: UtcDateTime
    end_at: UtcDateTime

    @model_validator(mode="after")
    def end_must_follow_start(self) -> AnalysisWindow:
        if self.end_at <= self.start_at:
            raise ValueError("analysis window end_at must follow start_at")
        return self


class PaymentEvent(ContractModel):
    """A payment event with privacy-safe references and extensible metadata."""

    event_id: Identifier = Field(
        description="Stable payment or provider-event identifier.",
    )
    merchant_id: Identifier
    occurred_at: UtcDateTime
    amount: Money
    currency: CurrencyCode
    payment_method: PaymentMethodType
    payment_status: PaymentStatus
    customer_reference: Identifier = Field(
        description="Privacy-safe token/reference; never raw customer PII.",
    )
    device_reference: Identifier = Field(
        description="Privacy-safe device token/reference; never raw device data.",
    )
    geography: CoarseGeography | None = None
    fraud_label: FraudLabel = FraudLabel.UNKNOWN
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class FraudSpikeIncident(ContractModel):
    """A merchant-level fraud-spike detection result."""

    incident_id: Identifier
    merchant_id: Identifier
    detected_at: UtcDateTime
    analysis_window: AnalysisWindow
    baseline_fraud_rate: Probability
    observed_fraud_rate: Probability
    deviation: Decimal
    affected_transaction_count: int = Field(ge=0)
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.DETECTED
    detector_version: Identifier
    confidence: Probability | None = None
    risk_score: Probability | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    suspicious_event_ids: list[Identifier] = Field(default_factory=list)
    investigation_notes: list[str] = Field(default_factory=list)
    resolution: str | None = None
    created_at: UtcDateTime | None = None
    updated_at: UtcDateTime | None = None


class EvidenceItem(ContractModel):
    """Structured, traceable evidence associated with an incident."""

    evidence_id: Identifier
    incident_id: Identifier
    category: EvidenceCategory
    metric: Identifier
    value: JsonValue
    baseline_value: JsonValue | None = None
    supporting_event_ids: list[Identifier] = Field(default_factory=list)
    window: AnalysisWindow | None = None
    confidence: Probability | None = None


class Investigation(ContractModel):
    """An investigation record that keeps conclusions tied to evidence."""

    investigation_id: Identifier
    incident_id: Identifier
    status: InvestigationStatus = InvestigationStatus.QUEUED
    started_at: UtcDateTime | None = None
    ended_at: UtcDateTime | None = None
    hypotheses: list[str] = Field(default_factory=list)
    evidence_ids: list[Identifier] = Field(default_factory=list)
    verification_result: VerificationResult | None = None
    confidence: Probability | None = None
    explanation: str | None = Field(default=None, max_length=20_000)
    recommended_defensive_response: str | None = Field(
        default=None,
        max_length=5_000,
    )

    @model_validator(mode="after")
    def end_must_follow_start(self) -> Investigation:
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at < self.started_at
        ):
            raise ValueError("ended_at cannot precede started_at")
        return self


class EvaluationResult(ContractModel):
    """Calculated results for a versioned, genuinely held-out test set.

    All counts and metrics remain nullable until an evaluation actually runs.
    """

    evaluation_id: Identifier
    dataset_version: Identifier
    held_out_test_set_id: Identifier
    detector_version: Identifier
    true_positives: int | None = Field(default=None, ge=0)
    true_negatives: int | None = Field(default=None, ge=0)
    false_positives: int | None = Field(default=None, ge=0)
    false_negatives: int | None = Field(default=None, ge=0)
    precision: Probability | None = None
    recall: Probability | None = None
    f1: Probability | None = None
    confusion_matrix: list[list[int]] | None = Field(default=None)
    test_set_size: int | None = Field(default=None, ge=0)
    false_positive_count: int | None = Field(default=None, ge=0)
    false_positive_cost: NonNegativeMoney | None = None
    evaluated_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def confusion_matrix_must_be_2x2_when_present(self) -> EvaluationResult:
        if self.confusion_matrix is not None:
            if len(self.confusion_matrix) != 2 or any(
                len(row) != 2 for row in self.confusion_matrix
            ):
                raise ValueError("confusion_matrix must be a 2x2 matrix")
        return self

    @model_validator(mode="after")
    def duplicate_false_positive_count_must_match(self) -> EvaluationResult:
        if (
            self.false_positive_count is not None
            and self.false_positives is not None
            and self.false_positive_count != self.false_positives
        ):
            raise ValueError(
                "false_positive_count must match false_positives when both are set",
            )
        return self


class AuditEvent(ContractModel):
    """Immutable audit entry for traceable defensive operations."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    event_id: Identifier
    occurred_at: UtcDateTime
    event_type: AuditEventType
    actor: Identifier | None = None
    source: Identifier | None = None
    incident_id: Identifier | None = None
    investigation_id: Identifier | None = None
    action: Identifier
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def actor_or_source_required(self) -> AuditEvent:
        if self.actor is None and self.source is None:
            raise ValueError("at least one of actor or source is required")
        return self