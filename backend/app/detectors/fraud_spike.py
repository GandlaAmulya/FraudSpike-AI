from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.schemas import (
    AnalysisWindow,
    FraudLabel,
    FraudSpikeIncident,
    IncidentSeverity,
    IncidentStatus,
    PaymentEvent,
)


class MerchantFraudSpikeDetector:
    """Merchant-level detector tuned for synthetic payment spikes.

    The detector uses a small set of transparent, explainable signals:
    - elevated fraud rate relative to the merchant's recent history
    - sustained transaction volume above the merchant's baseline
    - elevated amount values during the suspicious window
    - minimum fraud-event count to avoid flagging legitimate volume spikes
    """

    def __init__(
        self,
        *,
        baseline_window_days: int = 30,
        current_window_days: int = 7,
        min_transactions: int = 10,
        min_observed_rate: Decimal = Decimal("0.10"),
        threshold_multiplier: Decimal = Decimal("2.5"),
        minimum_fraud_events: int = 3,
        detector_version: str = "merchant-fraud-spike-v1",
    ) -> None:
        self.baseline_window_days = baseline_window_days
        self.current_window_days = current_window_days
        self.min_transactions = min_transactions
        self.min_observed_rate = min_observed_rate
        self.threshold_multiplier = threshold_multiplier
        self.minimum_fraud_events = minimum_fraud_events
        self.detector_version = detector_version

    def _merchant_activity(self, events: list[PaymentEvent]) -> dict[str, list[PaymentEvent]]:
        grouped: dict[str, list[PaymentEvent]] = defaultdict(list)
        for event in sorted(events, key=lambda item: item.occurred_at):
            grouped[event.merchant_id].append(event)
        return grouped

    def _fraud_rate(self, events: list[PaymentEvent]) -> Decimal:
        if not events:
            return Decimal("0")
        fraud_count = sum(
            1 for event in events if event.fraud_label is FraudLabel.FRAUDULENT
        )
        rate = Decimal(fraud_count) / Decimal(len(events))
        return rate.quantize(Decimal("0.000001"))

    def _average_amount(self, events: list[PaymentEvent]) -> Decimal:
        if not events:
            return Decimal("0")
        return (sum((event.amount for event in events), Decimal("0")) / Decimal(len(events))).quantize(Decimal("0.01"))

    def _should_flag(
        self,
        *,
        current_window: list[PaymentEvent],
        baseline_window: list[PaymentEvent],
        observed_rate: Decimal,
        baseline_rate: Decimal,
        current_volume: int,
        baseline_volume: int,
        current_avg_amount: Decimal,
        baseline_avg_amount: Decimal,
    ) -> bool:
        if not current_window:
            return False
        if current_volume < self.min_transactions:
            return False

        current_fraud_events = sum(
            1 for event in current_window if event.fraud_label is FraudLabel.FRAUDULENT
        )
        if current_fraud_events < self.minimum_fraud_events:
            return False

        if observed_rate < self.min_observed_rate:
            return False

        volume_ratio = Decimal(current_volume) / Decimal(max(baseline_volume, 1))
        amount_ratio = Decimal("1")
        if baseline_avg_amount > 0:
            amount_ratio = current_avg_amount / baseline_avg_amount

        baseline_trigger = baseline_rate > 0 and observed_rate >= max(
            self.min_observed_rate,
            baseline_rate * self.threshold_multiplier,
        )
        low_history_trigger = baseline_rate == 0 and observed_rate >= self.min_observed_rate and volume_ratio >= Decimal("1.4")
        multi_signal_trigger = (
            observed_rate >= max(self.min_observed_rate, baseline_rate * Decimal("1.7"))
            and volume_ratio >= Decimal("1.5")
            and amount_ratio >= Decimal("1.2")
        )

        return baseline_trigger or low_history_trigger or multi_signal_trigger

    def detect(self, events: list[PaymentEvent]) -> list[FraudSpikeIncident]:
        grouped = self._merchant_activity(events)
        incidents: list[FraudSpikeIncident] = []

        for merchant_id, merchant_events in grouped.items():
            merchant_events = sorted(merchant_events, key=lambda item: item.occurred_at)
            tzinfo = merchant_events[0].occurred_at.tzinfo

            for window_start in sorted({event.occurred_at.date() for event in merchant_events}):
                current_start = datetime.combine(window_start, datetime.min.time()).replace(
                    tzinfo=tzinfo,
                )
                current_end = current_start + timedelta(days=self.current_window_days)
                baseline_start = current_start - timedelta(days=self.baseline_window_days)

                current_window = [
                    event
                    for event in merchant_events
                    if current_start <= event.occurred_at < current_end
                ]
                baseline_window = [
                    event
                    for event in merchant_events
                    if baseline_start <= event.occurred_at < current_start
                ]
                if not current_window:
                    continue

                observed_rate = self._fraud_rate(current_window)
                baseline_rate = self._fraud_rate(baseline_window)
                current_avg_amount = self._average_amount(current_window)
                baseline_avg_amount = self._average_amount(baseline_window)
                current_volume = len(current_window)
                baseline_volume = len(baseline_window)
                deviation = observed_rate - baseline_rate

                if not self._should_flag(
                    current_window=current_window,
                    baseline_window=baseline_window,
                    observed_rate=observed_rate,
                    baseline_rate=baseline_rate,
                    current_volume=current_volume,
                    baseline_volume=baseline_volume,
                    current_avg_amount=current_avg_amount,
                    baseline_avg_amount=baseline_avg_amount,
                ):
                    continue

                severity = (
                    IncidentSeverity.CRITICAL
                    if observed_rate >= Decimal("0.40")
                    else IncidentSeverity.HIGH
                    if observed_rate >= Decimal("0.25")
                    else IncidentSeverity.MEDIUM
                )
                incidents.append(
                    FraudSpikeIncident(
                        incident_id=f"incident-{merchant_id}-{window_start.isoformat()}",
                        merchant_id=merchant_id,
                        detected_at=current_end,
                        analysis_window=AnalysisWindow(
                            start_at=current_start,
                            end_at=current_end,
                        ),
                        baseline_fraud_rate=baseline_rate,
                        observed_fraud_rate=observed_rate,
                        deviation=deviation,
                        affected_transaction_count=current_volume,
                        severity=severity,
                        status=IncidentStatus.DETECTED,
                        detector_version=self.detector_version,
                        confidence=Decimal("0.90"),
                        suspicious_event_ids=[
                            event.event_id
                            for event in current_window
                            if event.fraud_label is FraudLabel.FRAUDULENT
                        ],
                    )
                )

        return incidents


def _merchant_window_key(merchant_id: str, occurred_at: datetime) -> tuple[str, str]:
    return merchant_id, occurred_at.date().isoformat()


def _merchant_window_labels(events: list[PaymentEvent]) -> dict[tuple[str, str], int]:
    grouped: dict[tuple[str, str], list[PaymentEvent]] = defaultdict(list)
    for event in events:
        grouped[_merchant_window_key(event.merchant_id, event.occurred_at)].append(event)

    labels: dict[tuple[str, str], int] = {}
    for (merchant_id, window_day), window_events in grouped.items():
        fraud_count = sum(1 for event in window_events if event.fraud_label is FraudLabel.FRAUDULENT)
        if len(window_events) >= 10 and fraud_count >= 3 and (Decimal(fraud_count) / Decimal(len(window_events))) >= Decimal("0.10"):
            labels[(merchant_id, window_day)] = 1
        else:
            labels[(merchant_id, window_day)] = 0
    return labels


def _threshold_candidates() -> list[Decimal]:
    return [Decimal("1.5"), Decimal("2.0"), Decimal("2.5"), Decimal("3.0"), Decimal("4.0")]


def evaluate_merchant_spike_detector(
    split: dict[str, list[PaymentEvent]],
    *,
    detector_version: str = "merchant-fraud-spike-v1",
) -> dict[str, Any]:
    """Evaluate the merchant-window detector with strict train/validation/test separation.

    - train: used to build merchant baselines and detector configuration
    - validation: used for threshold selection only
    - test: used only for the final held-out evaluation
    """
    train_events = list(split.get("train", []))
    validation_events = list(split.get("validation", []))
    test_events = list(split.get("test", []))

    if not train_events and not validation_events and not test_events:
        raise ValueError("split must include at least one event across train, validation, and test")

    threshold = Decimal("2.5")
    best_f1 = Decimal("-1")
    best_fp = None

    if validation_events:
        candidate_labels = _merchant_window_labels(validation_events)
        for candidate in _threshold_candidates():
            detector = MerchantFraudSpikeDetector(
                threshold_multiplier=candidate,
                detector_version=f"{detector_version}-t{candidate}",
            )
            validation_predictions = {
                _merchant_window_key(event.merchant_id, event.occurred_at)
                for incident in detector.detect(validation_events)
                for event in validation_events
                if event.merchant_id == incident.merchant_id and event.occurred_at.date().isoformat() == incident.analysis_window.start_at.date().isoformat()
            }
            actual = [candidate_labels.get(key, 0) for key in sorted(candidate_labels)]
            predicted = [1 if key in validation_predictions else 0 for key in sorted(candidate_labels)]
            true_positives = sum(1 for actual_value, predicted_value in zip(actual, predicted) if actual_value == 1 and predicted_value == 1)
            false_positives = sum(1 for actual_value, predicted_value in zip(actual, predicted) if actual_value == 0 and predicted_value == 1)
            false_negatives = sum(1 for actual_value, predicted_value in zip(actual, predicted) if actual_value == 1 and predicted_value == 0)
            precision_denominator = true_positives + false_positives
            recall_denominator = true_positives + false_negatives
            precision = Decimal(true_positives) / Decimal(precision_denominator) if precision_denominator else Decimal("0")
            recall = Decimal(true_positives) / Decimal(recall_denominator) if recall_denominator else Decimal("0")
            f1 = Decimal("0") if (precision + recall) == 0 else (Decimal(2) * precision * recall) / (precision + recall)
            if f1 > best_f1 or (f1 == best_f1 and (best_fp is None or false_positives < best_fp)):
                threshold = candidate
                best_f1 = f1
                best_fp = false_positives

    final_detector = MerchantFraudSpikeDetector(
        threshold_multiplier=threshold,
        detector_version=detector_version,
    )

    final_incidents = final_detector.detect(train_events + validation_events + test_events)
    test_windows = _merchant_window_labels(test_events)
    predicted_windows = {
        _merchant_window_key(event.merchant_id, event.occurred_at)
        for incident in final_incidents
        for event in test_events
        if event.merchant_id == incident.merchant_id and event.occurred_at.date().isoformat() == incident.analysis_window.start_at.date().isoformat()
    }
    ordered_keys = sorted(test_windows)
    actual_labels = [test_windows.get(key, 0) for key in ordered_keys]
    predicted_labels = [1 if key in predicted_windows else 0 for key in ordered_keys]

    tp = sum(1 for actual_value, predicted_value in zip(actual_labels, predicted_labels) if actual_value == 1 and predicted_value == 1)
    fp = sum(1 for actual_value, predicted_value in zip(actual_labels, predicted_labels) if actual_value == 0 and predicted_value == 1)
    tn = sum(1 for actual_value, predicted_value in zip(actual_labels, predicted_labels) if actual_value == 0 and predicted_value == 0)
    fn = sum(1 for actual_value, predicted_value in zip(actual_labels, predicted_labels) if actual_value == 1 and predicted_value == 0)
    precision_denominator = tp + fp
    recall_denominator = tp + fn
    precision = Decimal(tp) / Decimal(precision_denominator) if precision_denominator else Decimal("0")
    recall = Decimal(tp) / Decimal(recall_denominator) if recall_denominator else Decimal("0")
    f1_score = Decimal("0") if (precision + recall) == 0 else (Decimal(2) * precision * recall) / (precision + recall)
    false_positive_cost = Decimal(fp) * Decimal("125.00")

    predictions = [
        {"merchant_id": merchant_id, "window_day": window_day, "predicted": int((merchant_id, window_day) in predicted_windows)}
        for merchant_id, window_day in ordered_keys
    ]

    return {
        "prediction_unit": "merchant_window",
        "threshold_policy": "validation-selected",
        "threshold": threshold,
        "train_event_count": len(train_events),
        "validation_event_count": len(validation_events),
        "test_event_count": len(test_events),
        "test_sample_count": len(actual_labels),
        "test_prediction_count": len(predictions),
        "predictions": predictions,
        "actual_labels": actual_labels,
        "predicted_labels": predicted_labels,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision.quantize(Decimal("0.000001")),
        "recall": recall.quantize(Decimal("0.000001")),
        "f1": f1_score.quantize(Decimal("0.000001")),
        "false_positive_cost": false_positive_cost.quantize(Decimal("0.01")),
        "detector_version": detector_version,
        "notes": "Train and validation define detector setup; test labels remain untouched until the final holdout evaluation.",
    }


def detect_merchant_spikes(events: list[PaymentEvent]) -> list[FraudSpikeIncident]:
    detector = MerchantFraudSpikeDetector()
    return detector.detect(events)
