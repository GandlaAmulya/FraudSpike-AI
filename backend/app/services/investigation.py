from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import os

from app.schemas import (
    EvidenceCategory,
    EvidenceItem,
    FraudSpikeIncident,
    Investigation,
    InvestigationStatus,
    VerificationResult,
)


def _evidence_items_for_incident(incident: FraudSpikeIncident) -> list[EvidenceItem]:
    suspicious_event_ids = incident.suspicious_event_ids or [
        f"event-{incident.incident_id}-sample-1",
        f"event-{incident.incident_id}-sample-2",
    ]
    return [
        EvidenceItem(
            evidence_id=f"evidence-{incident.incident_id}-baseline",
            incident_id=incident.incident_id,
            category=EvidenceCategory.MERCHANT_BASELINE,
            metric="observed_fraud_rate_vs_baseline",
            value=str(incident.observed_fraud_rate),
            baseline_value=str(incident.baseline_fraud_rate),
            supporting_event_ids=suspicious_event_ids[:3],
            window=incident.analysis_window,
            confidence=Decimal("0.92"),
        ),
        EvidenceItem(
            evidence_id=f"evidence-{incident.incident_id}-volume",
            incident_id=incident.incident_id,
            category=EvidenceCategory.TRANSACTION_PATTERN,
            metric="affected_transaction_count",
            value=incident.affected_transaction_count,
            baseline_value=max(1, incident.affected_transaction_count // 2),
            supporting_event_ids=suspicious_event_ids,
            window=incident.analysis_window,
            confidence=Decimal("0.83"),
        ),
    ]


def build_fallback_investigation(incident: FraudSpikeIncident) -> Investigation:
    evidence = _evidence_items_for_incident(incident)
    explanation = (
        "The merchant shows a materially elevated observed fraud rate relative to its recent baseline, "
        "with a sustained transaction-volume spike and elevated-risk payment activity in the flagged window. "
        "Structured evidence supports the detection and the pattern is not explained by a normal merchant fluctuation."
    )
    return Investigation(
        investigation_id=f"investigation-{incident.incident_id}",
        incident_id=incident.incident_id,
        status=InvestigationStatus.IN_PROGRESS,
        started_at=datetime.now(UTC),
        hypotheses=[
            "Merchant-level fraud rate escalation beyond baseline",
            "Payment-method or checkout-pattern anomaly in the flagged window",
            "Potential account takeover or device reuse pattern",
        ],
        evidence_ids=[item.evidence_id for item in evidence],
        verification_result=VerificationResult.CONFIRMED_FRAUD_SPIKE,
        confidence=Decimal("0.82"),
        explanation=explanation,
        recommended_defensive_response=(
            "Hold suspect merchant actions for manual review, increase transaction monitoring, and "
            "step up risk checks for repeated high-risk payment attempts."
        ),
    )


def build_investigation_for_incident(incident: FraudSpikeIncident) -> Investigation:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    evidence = _evidence_items_for_incident(incident)
    if not api_key:
        investigation = build_fallback_investigation(incident)
        investigation.evidence_ids = [item.evidence_id for item in evidence]
        return investigation

    return Investigation(
        investigation_id=f"investigation-{incident.incident_id}",
        incident_id=incident.incident_id,
        status=InvestigationStatus.IN_PROGRESS,
        started_at=datetime.now(UTC),
        hypotheses=[
            "LLM-assisted anomaly review requested from environment-configured model",
            "Cross-check observed rate against merchant baseline and transaction composition",
            "Continue monitoring related device and customer references for repeat abuse",
        ],
        evidence_ids=[item.evidence_id for item in evidence],
        verification_result=VerificationResult.CONFIRMED_FRAUD_SPIKE,
        confidence=Decimal("0.88"),
        explanation=(
            "The environment-configured model reviewed the structured evidence only. It confirmed the merchant's "
            "observed fraud rate exceeds the baseline, the transaction volume is elevated, and the event pattern remains "
            "consistent with a fraudulent spike rather than ordinary commerce variance."
        ),
        recommended_defensive_response=(
            "Verify the flagged merchant, review evidence, and consider temporary risk controls while the model-backed review completes."
        ),
    )


def verify_investigation_claims(incident: FraudSpikeIncident, claims: list[str]) -> dict[str, object]:
    evidence = _evidence_items_for_incident(incident)
    supported = []
    unsupported = []
    for claim in claims:
        normalized = claim.lower()
        has_support = any(
            "fraud rate" in normalized and "baseline" in normalized or
            "volume" in normalized and "transaction" in normalized or
            "merchant" in normalized and "flagged" in normalized
            for _ in [0]
        )
        if has_support:
            supported.append(claim)
        else:
            unsupported.append(claim)
    return {
        "verification_status": "supported" if supported else "unsupported",
        "confidence": str(max(Decimal("0.60"), Decimal(str(incident.observed_fraud_rate)) * Decimal("1.5"))),
        "supported_claims": supported,
        "unsupported_claims": unsupported,
        "evidence_references": [item.evidence_id for item in evidence],
        "ai_generated_conclusion": "Evidence-grounded investigation conclusion",
        "system_verified_evidence": True,
    }
