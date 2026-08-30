"""Held-out evaluation and honest metric calculation boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Sequence

from app.schemas import EvaluationResult

_DEFAULT_FALSE_POSITIVE_COST = Decimal("125.00")


def _normalize_binary_labels(
    labels: Sequence[int | bool],
    label_name: str,
) -> list[int]:
    """Translate boolean or 0/1 labels into deterministic binary integers."""
    normalized: list[int] = []

    for index, value in enumerate(labels):
        if isinstance(value, bool):
            normalized.append(int(value))
        elif isinstance(value, int) and value in (0, 1):
            normalized.append(value)
        else:
            raise ValueError(
                f"{label_name} labels must be binary values (0/1 or bool) at index {index}; "
                f"received {value!r}",
            )

    return normalized


def evaluate_held_out_predictions(
    actual_labels: Sequence[int | bool],
    predicted_labels: Sequence[int | bool],
    *,
    dataset_version: str,
    held_out_test_set_id: str,
    detector_version: str,
    false_positive_cost_per_case: Decimal | int | float | None = None,
) -> EvaluationResult:
    """Evaluate a genuinely held-out test split without tuning on the final labels.

    Cost assumption: each false positive is assumed to cost $125.00 in direct
    recovery/testing overhead. This value is explicit, documented, and reproducible.
    """

    actual = _normalize_binary_labels(actual_labels, "actual")
    predicted = _normalize_binary_labels(predicted_labels, "predicted")

    if len(actual) != len(predicted):
        raise ValueError("actual_labels and predicted_labels must be the same length")
    if len(actual) == 0:
        raise ValueError("held-out evaluation requires at least one row")

    true_positives = sum(
        1
        for actual_value, predicted_value in zip(actual, predicted)
        if actual_value == 1 and predicted_value == 1
    )
    true_negatives = sum(
        1
        for actual_value, predicted_value in zip(actual, predicted)
        if actual_value == 0 and predicted_value == 0
    )
    false_positives = sum(
        1
        for actual_value, predicted_value in zip(actual, predicted)
        if actual_value == 0 and predicted_value == 1
    )
    false_negatives = sum(
        1
        for actual_value, predicted_value in zip(actual, predicted)
        if actual_value == 1 and predicted_value == 0
    )

    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives
    precision = (
        Decimal(true_positives) / Decimal(precision_denominator)
        if precision_denominator
        else Decimal("0")
    ).quantize(Decimal("0.000001"))
    recall = (
        Decimal(true_positives) / Decimal(recall_denominator)
        if recall_denominator
        else Decimal("0")
    ).quantize(Decimal("0.000001"))
    if precision + recall == 0:
        f1 = Decimal("0")
    else:
        f1 = (
            (Decimal(2) * precision * recall) / (precision + recall)
        ).quantize(Decimal("0.000001"))

    if false_positive_cost_per_case is None:
        false_positive_cost_decimal = _DEFAULT_FALSE_POSITIVE_COST
    elif isinstance(false_positive_cost_per_case, Decimal):
        false_positive_cost_decimal = false_positive_cost_per_case
    else:
        false_positive_cost_decimal = Decimal(str(false_positive_cost_per_case))

    false_positive_cost = (
        Decimal(false_positives) * false_positive_cost_decimal
    ).quantize(Decimal("0.01"))

    evaluated_at = datetime.now(UTC)

    return EvaluationResult(
        evaluation_id=(
            f"eval-{dataset_version}-{held_out_test_set_id}-{detector_version}-"
            f"{evaluated_at.strftime('%Y%m%dT%H%M%SZ')}"
        ),
        dataset_version=dataset_version,
        held_out_test_set_id=held_out_test_set_id,
        detector_version=detector_version,
        true_positives=true_positives,
        true_negatives=true_negatives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
        confusion_matrix=[[true_positives, false_positives], [false_negatives, true_negatives]],
        test_set_size=len(actual),
        false_positive_count=false_positives,
        false_positive_cost=false_positive_cost,
        evaluated_at=evaluated_at,
    )


__all__ = [
    "_DEFAULT_FALSE_POSITIVE_COST",
    "evaluate_held_out_predictions",
]