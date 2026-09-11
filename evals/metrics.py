"""
Evaluation metrics for CodeSentinel AI.

Matching algorithm:
  A prediction matches a ground truth if ALL of:
  1. file paths match exactly (case-sensitive)
  2. abs(predicted_line - expected_line) <= LINE_TOLERANCE
  3. category matches exactly

Documented limitations:
  - LINE_TOLERANCE=5 can cause false matches for dense bugs (<5 lines apart).
  - Category matching is strict: model must emit the correct enum string.
  - File path matching is case-sensitive and path-separator-sensitive.
  - Greedy matching: first valid match wins (not optimal assignment).

These limitations are intentional for MVP simplicity. The matching function
is isolated here so it can be replaced with Hungarian-algorithm optimal
assignment or semantic similarity in future iterations.
"""
from dataclasses import dataclass
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


@dataclass
class Prediction:
    """One finding produced by the reviewer."""
    id: str
    file: str
    line: int | None
    category: str
    confidence: float


class MatchResult(NamedTuple):
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    matched_pairs: list[tuple[str, str]]  # [(truth_id, pred_id), ...]


def _matches(truth: GroundTruth, pred: Prediction) -> bool:
    """Return True if pred is a valid detection of truth.
    
    All three conditions must hold simultaneously.
    """
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
    """Calculate precision, recall, and F1 for a prediction set.
    
    Uses greedy matching: for each ground truth (in order), find the first
    unmatched prediction that satisfies _matches(). This is O(n*m) and
    sufficient for small evaluation sets.
    
    Args:
        truths: Ground truth defects.
        predictions: Reviewer predictions.
        
    Returns:
        MatchResult with TP, FP, FN, precision, recall, F1, matched pairs.
    """
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
