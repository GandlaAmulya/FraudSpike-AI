from decimal import Decimal

import pytest

from app.evaluation import evaluate_held_out_predictions


def test_evaluate_held_out_predictions_returns_confusion_matrix_and_metrics() -> None:
    actual = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    predicted = [1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 1, 0]

    result = evaluate_held_out_predictions(
        actual_labels=actual,
        predicted_labels=predicted,
        dataset_version="dataset-v1",
        held_out_test_set_id="held-out-v1",
        detector_version="detector-v1",
        false_positive_cost_per_case=Decimal("125.00"),
    )

    assert result.true_positives == 3
    assert result.true_negatives == 5
    assert result.false_positives == 1
    assert result.false_negatives == 3
    assert result.precision == Decimal("0.750000")
    assert result.recall == Decimal("0.500000")
    assert result.f1 == Decimal("0.600000")
    assert result.false_positive_cost == Decimal("125.00")
    assert result.evaluated_at is not None

    confusion = result.confusion_matrix
    assert confusion == [[3, 1], [3, 5]]
    assert result.test_set_size == 12


def test_evaluate_held_out_predictions_rejects_invalid_binary_inputs() -> None:
    with pytest.raises(ValueError, match="binary"):
        evaluate_held_out_predictions(
            actual_labels=[1, 0, 2],
            predicted_labels=[1, 0, 0],
            dataset_version="dataset-v1",
            held_out_test_set_id="held-out-v1",
            detector_version="detector-v1",
        )

    with pytest.raises(ValueError, match="same length"):
        evaluate_held_out_predictions(
            actual_labels=[1, 0, 1],
            predicted_labels=[1, 0],
            dataset_version="dataset-v1",
            held_out_test_set_id="held-out-v1",
            detector_version="detector-v1",
        )
