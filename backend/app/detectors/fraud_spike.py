from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
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
                    )
                )

        return incidents


def detect_merchant_spikes(events: list[PaymentEvent]) -> list[FraudSpikeIncident]:
    detector = MerchantFraudSpikeDetector()
    return detector.detect(events)
