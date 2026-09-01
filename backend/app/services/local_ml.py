from __future__ import annotations

from decimal import Decimal

from app.schemas import FraudLabel, PaymentEvent


class LocalAnomalyModel:
    """Small deterministic anomaly score grounded in local transaction patterns.

    This intentionally remains lightweight and explainable. It is not a production ML model,
    but it gives the investigation workflow a local, evidence-backed signal without inventing
    data or claiming hidden model intelligence.
    """

    model_version = "local-anomaly-v1"

    def score(self, events: list[PaymentEvent]) -> dict[str, object]:
        if not events:
            return {
                "status": "ok",
                "anomaly_score": 0.0,
                "model_version": self.model_version,
                "signals": ["insufficient_history"],
                "notes": "No transaction history was available for local anomaly scoring.",
            }

        fraudulent_events = [event for event in events if event.fraud_label is FraudLabel.FRAUDULENT]
        fraud_ratio = Decimal(len(fraudulent_events)) / Decimal(len(events))
        avg_amount = sum((event.amount for event in events), Decimal("0")) / Decimal(len(events))
        amount_ratio = min(Decimal("1.0"), avg_amount / Decimal("1000.00"))
        duration_hours = Decimal(str(max(1.0, (events[-1].occurred_at - events[0].occurred_at).total_seconds() / 3600)))
        volume_density = min(Decimal("1.0"), Decimal(len(events)) / (duration_hours * Decimal("5")))
        score = Decimal("0.15")
        score += fraud_ratio * Decimal("0.55")
        score += amount_ratio * Decimal("0.20")
        score += volume_density * Decimal("0.10")
        score = min(Decimal("0.99"), max(Decimal("0.00"), score))

        return {
            "status": "ok",
            "anomaly_score": float(score.quantize(Decimal("0.0001"))),
            "model_version": self.model_version,
            "signals": ["fraud_ratio", "amount_elevation", "transaction_density"],
            "notes": "Scores are derived strictly from local transaction patterns and observed labels.",
        }
