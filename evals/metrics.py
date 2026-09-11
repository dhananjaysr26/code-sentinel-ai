"""
Evaluation metrics for CodeSentinel AI.

Matching algorithm:
  A prediction matches a ground truth if ALL of:
  1. file paths match exactly (case-sensitive)
  2. abs(predicted_line - expected_line) <= LINE_TOLERANCE
  3. category matches exactly

Per-category metrics are reported separately for:
  - correctness
  - security

Per-subcategory recall is also reported to identify specific weak spots.

Documented limitations:
  - LINE_TOLERANCE=5 can cause false matches for dense bugs (<5 lines apart).
  - Category matching is strict: model must emit the correct enum string.
  - File path matching is case-sensitive and path-separator-sensitive.
  - Greedy matching: first valid match wins (not optimal assignment).
"""
from dataclasses import dataclass, field
from typing import NamedTuple

LINE_TOLERANCE = 5  # lines of slack around expected_line


@dataclass
class GroundTruth:
    """One known defect in the evaluation dataset."""
    id: str
    category: str
    file: str
    expected_line: int
    description: str
    severity: str
    subcategory: str = ""


@dataclass
class Prediction:
    """One finding produced by a reviewer."""
    id: str
    file: str
    line: int | None
    category: str
    confidence: float
    subcategory: str = ""
    reviewer: str = ""


class MatchResult(NamedTuple):
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    matched_pairs: list[tuple[str, str]]  # [(truth_id, pred_id), ...]


def _matches(truth: GroundTruth, pred: Prediction) -> bool:
    """Return True if pred is a valid detection of truth."""
    if truth.file != pred.file:
        return False
    if truth.category != pred.category:
        return False
    if pred.line is None:
        return False
    return abs(truth.expected_line - pred.line) <= LINE_TOLERANCE


def calculate_metrics(
    truths: list[GroundTruth],
    predictions: list[Prediction],
) -> MatchResult:
    """Calculate precision, recall, and F1 for a prediction set."""
    matched_pred_ids: set[str] = set()
    matched_pairs: list[tuple[str, str]] = []

    for truth in truths:
        for pred in predictions:
            if pred.id in matched_pred_ids:
                continue
            if _matches(truth, pred):
                matched_pred_ids.add(pred.id)
                matched_pairs.append((truth.id, pred.id))
                break

    tp = len(matched_pairs)
    fp = len(predictions) - tp
    fn = len(truths) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return MatchResult(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        matched_pairs=matched_pairs,
    )


def calculate_metrics_by_category(
    truths: list[GroundTruth],
    predictions: list[Prediction],
) -> dict[str, MatchResult]:
    """Calculate metrics separately for each category.

    Returns a dict keyed by category string, e.g. {'correctness': ..., 'security': ...}
    """
    categories = set(t.category for t in truths)
    results = {}
    for cat in categories:
        cat_truths = [t for t in truths if t.category == cat]
        cat_preds = [p for p in predictions if p.category == cat]
        results[cat] = calculate_metrics(cat_truths, cat_preds)
    return results


def calculate_recall_by_subcategory(
    truths: list[GroundTruth],
    predictions: list[Prediction],
) -> dict[str, float]:
    """Calculate recall broken down by subcategory.

    Useful for identifying specific bug types the model misses.
    Returns a dict keyed by subcategory string.
    """
    subcategories = set(t.subcategory for t in truths if t.subcategory)
    recall_by_sub = {}
    for sub in sorted(subcategories):
        sub_truths = [t for t in truths if t.subcategory == sub]
        result = calculate_metrics(sub_truths, predictions)
        recall_by_sub[sub] = result.recall
    return recall_by_sub
