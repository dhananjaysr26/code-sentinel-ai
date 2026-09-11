#!/usr/bin/env python3
"""
Evaluation runner for CodeSentinel AI.

Usage:
    python evals/run_eval.py [--repo-path evals/seed_repo] [--base-ref HEAD~1]

This script:
1. Calls the Django API to run a review on the seed repo.
2. Collects findings.
3. Matches against ground truth fixtures.
4. Calculates and prints precision/recall/F1.
5. Writes results to evals/results/eval_results.json.

The API server must be running at CODESENTINEL_API (default: http://localhost:8000).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

# Add project root to path so we can import evals.metrics
_EVALS_DIR = Path(__file__).parent
_PROJECT_ROOT = _EVALS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from evals.metrics import GroundTruth, Prediction, calculate_metrics

API_BASE = os.environ.get("CODESENTINEL_API", "http://localhost:8000")
DEFAULT_REPO = str(_EVALS_DIR / "seed_repo")


def load_ground_truth(fixtures_dir: Path) -> list[GroundTruth]:
    data = json.loads((fixtures_dir / "defects.json").read_text())
    return [GroundTruth(**item) for item in data]


def run_review(repo_path: str, base_ref: str, target_ref: str) -> dict:
    """Call the Django API and return the full response dict."""
    url = f"{API_BASE}/api/reviews/"
    payload = {
        "repo_path": str(Path(repo_path).resolve()),
        "base_ref": base_ref,
        "target_ref": target_ref,
        "llm_provider": "bedrock",
    }
    print(f"POST {url}")
    print(f"  repo_path:  {payload['repo_path']}")
    print(f"  base_ref:   {base_ref}")
    print(f"  target_ref: {target_ref}")

    resp = requests.post(url, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()


def findings_to_predictions(findings: list[dict]) -> list[Prediction]:
    return [
        Prediction(
            id=f["id"],
            file=f["file"],
            line=f.get("line"),
            category=f["category"],
            confidence=f["confidence"],
        )
        for f in findings
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CodeSentinel AI evaluation")
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--base-ref", default="HEAD~1")
    parser.add_argument("--target-ref", default="HEAD")
    parser.add_argument(
        "--output",
        default=str(_EVALS_DIR / "results" / "eval_results.json"),
    )
    args = parser.parse_args()

    fixtures_dir = _EVALS_DIR / "fixtures"
    truths = load_ground_truth(fixtures_dir)
    print(f"\nGround truth: {len(truths)} seeded defects")

    try:
        review_data = run_review(args.repo_path, args.base_ref, args.target_ref)
    except requests.ConnectionError:
        print(f"\nERROR: Cannot connect to {API_BASE}. Is the Django server running?")
        sys.exit(1)
    except requests.HTTPError as exc:
        print(f"\nERROR: API returned {exc.response.status_code}: {exc.response.text}")
        sys.exit(1)

    status = review_data.get("status")
    findings_raw = review_data.get("findings", [])
    errors = review_data.get("errors", [])

    print(f"\nReview status: {status}")
    print(f"Findings:      {len(findings_raw)}")
    if errors:
        print(f"Errors:        {errors}")

    predictions = findings_to_predictions(findings_raw)
    result = calculate_metrics(truths, predictions)

    print("\n=== EVALUATION RESULTS ===")
    print(f"True Positives:  {result.true_positives} / {len(truths)}")
    print(f"False Positives: {result.false_positives}")
    print(f"False Negatives: {result.false_negatives}")
    print(f"Precision:       {result.precision:.4f}")
    print(f"Recall:          {result.recall:.4f}")
    print(f"F1:              {result.f1:.4f}")

    if result.matched_pairs:
        print("\nMatched pairs (truth_id → pred_id):")
        for tid, pid in result.matched_pairs:
            print(f"  {tid} → {pid}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "review_id": review_data.get("id"),
        "repo_path": args.repo_path,
        "base_ref": args.base_ref,
        "target_ref": args.target_ref,
        "status": status,
        "true_positives": result.true_positives,
        "false_positives": result.false_positives,
        "false_negatives": result.false_negatives,
        "precision": result.precision,
        "recall": result.recall,
        "f1": result.f1,
        "matched_pairs": result.matched_pairs,
        "predictions": [p.__dict__ for p in predictions],
        "errors": errors,
    }
    output_path.write_text(json.dumps(output_data, indent=2))
    print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
