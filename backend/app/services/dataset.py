from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import random
from typing import Any

from app.schemas import (
    CoarseGeography,
    FraudLabel,
    PaymentEvent,
    PaymentMethodType,
    PaymentStatus,
)


def build_demo_dataset() -> list[PaymentEvent]:
    """Create a deterministic synthetic merchant-risk dataset with real holdout fraud spikes.

    Design notes:
    - The dataset is fixed-seed and reproducible.
    - Training data is used for merchant baselines and detector tuning.
    - The held-out test window contains actual fraudulent merchant-level spikes.
    - Legitimate spikes are present but remain non-fraudulent and should not be flagged by the detector.
    """
    rng = random.Random(42)
    merchants = [
        {
            "merchant_id": "merchant-001",
            "base_volume": 12,
            "amount_mean": Decimal("420.00"),
            "region": "KA",
        },
        {
            "merchant_id": "merchant-002",
            "base_volume": 18,
            "amount_mean": Decimal("680.00"),
            "region": "KA",
        },
        {
            "merchant_id": "merchant-003",
            "base_volume": 16,
            "amount_mean": Decimal("540.00"),
            "region": "MH",
        },
        {
            "merchant_id": "merchant-004",
            "base_volume": 10,
            "amount_mean": Decimal("930.00"),
            "region": "DL",
        },
        {
            "merchant_id": "merchant-005",
            "base_volume": 22,
            "amount_mean": Decimal("770.00"),
            "region": "MH",
        },
        {
            "merchant_id": "merchant-006",
            "base_volume": 14,
            "amount_mean": Decimal("610.00"),
            "region": "TN",
        },
    ]
    suspicious_merchants = {"merchant-002", "merchant-005"}
    legitimate_spike_merchants = {"merchant-003", "merchant-006"}
    start_day = date(2025, 1, 1)
    events: list[PaymentEvent] = []

    for merchant in merchants:
        merchant_id = merchant["merchant_id"]
        base_volume = merchant["base_volume"]
        amount_mean = merchant["amount_mean"]
        region = merchant["region"]

        for offset in range(120):
            current_day = start_day + timedelta(days=offset)
            base_transactions = base_volume + rng.randint(0, 8)
            legitimate_spike = merchant_id in legitimate_spike_merchants and 20 <= offset <= 28
            suspicious_window = merchant_id in suspicious_merchants and 108 <= offset <= 118

            transaction_count = base_transactions
            if legitimate_spike:
                transaction_count += 16 + rng.randint(0, 10)
            if suspicious_window:
                transaction_count += 18 + rng.randint(0, 12)

            for event_index in range(transaction_count):
                event_time = datetime(
                    current_day.year,
                    current_day.month,
                    current_day.day,
                    8 + (event_index * 2) % 12,
                    rng.randint(0, 59),
                    tzinfo=UTC,
                )

                if suspicious_window:
                    fraud_probability = 0.34 + rng.random() * 0.18
                    is_fraud = rng.random() < fraud_probability
                elif legitimate_spike:
                    is_fraud = False
                else:
                    is_fraud = rng.random() < 0.01 + (0.003 if merchant_id in suspicious_merchants else 0)

                amount = (
                    amount_mean
                    + Decimal(str(rng.uniform(-120, 240)))
                    + (Decimal("240") if suspicious_window and is_fraud else Decimal("0"))
                    + (Decimal("80") if legitimate_spike else Decimal("0"))
                ).quantize(Decimal("0.01"))

                events.append(
                    PaymentEvent(
                        event_id=f"evt-{merchant_id}-{offset}-{event_index}",
                        merchant_id=merchant_id,
                        occurred_at=event_time,
                        amount=amount,
                        currency="INR",
                        payment_method=PaymentMethodType.UPI if rng.random() < 0.6 else PaymentMethodType.CARD,
                        payment_status=PaymentStatus.CAPTURED,
                        customer_reference=f"customer-{rng.randint(1, 250)}",
                        device_reference=f"device-{rng.randint(1, 500)}",
                        geography=CoarseGeography(
                            country_code="IN",
                            region_code=region,
                        ),
                        fraud_label=(
                            FraudLabel.FRAUDULENT if is_fraud else FraudLabel.LEGITIMATE
                        ),
                        metadata={
                            "channel": "checkout",
                            "retry_count": rng.randint(0, 2),
                            "merchant_segment": "retail",
                            "risk_bucket": "elevated" if is_fraud else "normal",
                            "legitimate_spike": legitimate_spike,
                            "suspicious_window": suspicious_window,
                        },
                    )
                )

    events.sort(key=lambda item: item.occurred_at)
    return events


def split_events_by_period(events: list[PaymentEvent]) -> dict[str, list[PaymentEvent]]:
    train_cutoff = datetime(2025, 2, 28, tzinfo=UTC)
    validation_cutoff = datetime(2025, 4, 15, tzinfo=UTC)

    train = [event for event in events if event.occurred_at < train_cutoff]
    validation = [
        event
        for event in events
        if train_cutoff <= event.occurred_at < validation_cutoff
    ]
    test = [event for event in events if event.occurred_at >= validation_cutoff]

    return {
        "train": train,
        "validation": validation,
        "test": test,
    }


def evaluate_window_predictions(
    events: list[PaymentEvent],
    merchant_predictions: dict[str, bool],
) -> tuple[list[int], list[int]]:
    merchant_totals: defaultdict[str, list[PaymentEvent]] = defaultdict(list)
    for event in events:
        merchant_totals[event.merchant_id].append(event)

    actual: list[int] = []
    predicted: list[int] = []
    for merchant_id, merchant_events in sorted(merchant_totals.items()):
        actual_flag = 1 if any(event.fraud_label is FraudLabel.FRAUDULENT for event in merchant_events) else 0
        predicted_flag = 1 if merchant_predictions.get(merchant_id, False) else 0
        actual.append(actual_flag)
        predicted.append(predicted_flag)

    return actual, predicted
