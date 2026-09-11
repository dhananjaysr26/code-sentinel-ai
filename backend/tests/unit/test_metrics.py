"""Unit tests for the evaluation metrics module."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from evals.metrics import (
    GroundTruth, Prediction, calculate_metrics, LINE_TOLERANCE
)


def make_truth(id="t1", file="src/a.py", line=10, category="correctness"):
    return GroundTruth(
        id=id, category=category, file=file, expected_line=line,
        description="test bug", severity="HIGH"
    )


def make_pred(id="p1", file="src/a.py", line=10, category="correctness", conf=0.9):
    return Prediction(id=id, file=file, line=line, category=category, confidence=conf)


def test_perfect_match():
    truths = [make_truth()]
    preds = [make_pred()]
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 1
    assert result.false_positives == 0
    assert result.false_negatives == 0
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0


def test_no_match():
    truths = [make_truth(file="src/a.py")]
    preds = [make_pred(file="src/b.py")]  # different file
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.false_negatives == 1
    assert result.precision == 0.0
    assert result.recall == 0.0


def test_empty_predictions():
    truths = [make_truth()]
    result = calculate_metrics(truths, [])
    assert result.true_positives == 0
    assert result.false_negatives == 1
    assert result.precision == 0.0
    assert result.recall == 0.0


def test_empty_truths():
    preds = [make_pred()]
    result = calculate_metrics([], preds)
    assert result.true_positives == 0
    assert result.false_positives == 1
    assert result.precision == 0.0
    assert result.recall == 0.0


def test_line_within_tolerance():
    truths = [make_truth(line=10)]
    preds = [make_pred(line=10 + LINE_TOLERANCE)]  # exactly at boundary
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 1


def test_line_outside_tolerance():
    truths = [make_truth(line=10)]
    preds = [make_pred(line=10 + LINE_TOLERANCE + 1)]  # one past boundary
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 0


def test_category_mismatch():
    truths = [make_truth(category="correctness")]
    preds = [make_pred(category="security")]
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 0


def test_mixed_results():
    truths = [make_truth("t1"), make_truth("t2", file="src/b.py", line=20)]
    preds = [
        make_pred("p1"),              # matches t1
        make_pred("p2", file="src/c.py"),  # no match (FP)
    ]
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 1
    assert result.false_positives == 1
    assert result.false_negatives == 1
    assert result.precision == 0.5
    assert result.recall == 0.5


def test_prediction_not_matched_twice():
    """One prediction should not match two ground truths."""
    truths = [make_truth("t1", line=10), make_truth("t2", line=10)]
    preds = [make_pred("p1", line=10)]
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 1  # p1 matches t1 only
    assert result.false_negatives == 1  # t2 unmatched


def test_none_line_does_not_match():
    truths = [make_truth(line=10)]
    preds = [make_pred(line=None)]
    result = calculate_metrics(truths, preds)
    assert result.true_positives == 0
