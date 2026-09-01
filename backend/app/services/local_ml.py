from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.schemas import FraudLabel, PaymentEvent

try:
    from sklearn.ensemble import IsolationForest
except Exception:  # pragma: no cover - dependency is installed in the project environment
    IsolationForest = None  # type: ignore[assignment]


class LocalAnomalyAgent:
    """Local Isolation Forest anomaly agent for investigation support only."""

    model = "IsolationForest"
    model_version = "local-isolation-forest-v1"
    minimum_evidence = 8

    def _event_features(self, events: list[PaymentEvent]) -> tuple[list[list[float]], list[str]]:
        feature_names = [
            "amount",
            "amount_ratio_to_merchant_mean",
            "velocity_1h",
            "device_repeat_count",
            "hour_of_day",
            "fraud_label_seen",
        ]
        if not events:
            return [], feature_names

        merchant_events = sorted(events, key=lambda item: item.occurred_at)
        mean_amount = sum((event.amount for event in merchant_events), Decimal("0")) / Decimal(len(merchant_events))
        merchant_mean = float(mean_amount) if mean_amount > 0 else 1.0
        device_counts: dict[str, int] = defaultdict(int)
        for event in merchant_events:
            device_counts[event.device_reference] += 1

        rows: list[list[float]] = []
        for event in merchant_events:
            window_start = event.occurred_at - timedelta(hours=1)
            velocity_1h = sum(
                1
                for prior in merchant_events
                if window_start <= prior.occurred_at <= event.occurred_at
            )
            amount_ratio = (float(event.amount) / merchant_mean) if merchant_mean else 1.0
            rows.append(
                [
                    float(event.amount),
                    amount_ratio,
                    float(velocity_1h),
                    float(device_counts.get(event.device_reference, 0)),
                    float(event.occurred_at.hour),
                    1.0 if event.fraud_label is FraudLabel.FRAUDULENT else 0.0,
                ]
            )
        return rows, feature_names

    def analyze(self, events: list[PaymentEvent]) -> dict[str, object]:
        if len(events) < self.minimum_evidence:
            return {
                "model": self.model,
                "model_version": self.model_version,
                "available": False,
                "anomaly_score": None,
                "assessment": "INSUFFICIENT_EVIDENCE",
                "features_used": [],
                "evidence_references": [],
                "reasoning_summary": "Insufficient evidence: the merchant does not have enough persisted transaction history for a meaningful local Isolation Forest assessment.",
                "limitations": ["Insufficient persisted transaction evidence for local ML analysis."],
            }

        rows, features_used = self._event_features(events)
        if not rows or IsolationForest is None:
            return {
                "model": self.model,
                "model_version": self.model_version,
                "available": False,
                "anomaly_score": None,
                "assessment": "INSUFFICIENT_EVIDENCE",
                "features_used": features_used,
                "evidence_references": [f"transaction:{event.event_id}" for event in events[:5]],
                "reasoning_summary": "Insufficient evidence: the local Isolation Forest library or persisted merchant evidence is not available for this merchant.",
                "limitations": ["No local model runtime available for inference."],
            }

        model = IsolationForest(contamination=0.15, random_state=42, n_estimators=200)
        model.fit(rows)
        row_scores = model.score_samples(rows)
        min_score = min(row_scores)
        max_score = max(row_scores)
        span = (max_score - min_score) or 1.0
        anomaly_scores = [float((max_score - score) / span) for score in row_scores]
        max_anomaly = max(anomaly_scores) if anomaly_scores else 0.0
        assessment = "ANOMALOUS" if max_anomaly >= 0.60 else "NOT_ANOMALOUS"

        return {
            "model": self.model,
            "model_version": self.model_version,
            "available": True,
            "anomaly_score": round(max_anomaly, 4),
            "assessment": assessment,
            "features_used": features_used,
            "evidence_references": [f"transaction:{event.event_id}" for event in events[:8]],
            "reasoning_summary": "The local Isolation Forest was fit on persisted merchant transaction features and produced a relative anomaly signal using amount, velocity, device reuse, and timing patterns.",
            "limitations": [
                "This is a local anomaly signal, not a calibrated fraud probability.",
                "It is supplementary evidence for analyst review and does not automate payment decisions.",
            ],
        }


LocalAnomalyModel = LocalAnomalyAgent
