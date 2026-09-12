#!/usr/bin/env python3
"""
Evaluation runner for CodeSentinel AI.

Usage:
    python evals/run_eval.py [--repo-path evals/seed_repo] [--base-ref HEAD~1]

This script:
1. Calls the Django API to run a review on the seed repo.
2. Collects findings.
3. Matches against ground truth fixtures.
4. Calculates and prints precision/recall/F1 overall and per-category.
5. Reports per-subcategory recall.
6. Writes results to evals/results/eval_results.json.

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

from evals.metrics import (
    GroundTruth, Prediction,
    calculate_metrics, calculate_metrics_by_category, calculate_recall_by_subcategory,
)

API_BASE = os.environ.get("CODESENTINEL_API", "http://localhost:8000")
DEFAULT_REPO = str(_PROJECT_ROOT.parent / "seed_repo")


def load_ground_truth(fixtures_dir: Path, repo_path: str) -> list[GroundTruth]:
    if "auth-bypass" in repo_path:
        path = fixtures_dir / "auth-bypass" / "ground_truth.json"
    elif "multi-loop" in repo_path:
        path = fixtures_dir / "multi-loop" / "ground_truth.json"
    else:
        path = fixtures_dir / "seed_repo" / "ground_truth.json"
    data = json.loads(path.read_text())
    return [GroundTruth(**item) for item in data]


def run_review(repo_path: str, base_ref: str, target_ref: str) -> dict:
    """Call the Django API and return the full response dict."""
    url = f"{API_BASE}/api/reviews/"
    payload = {
        "repo_path": str(repo_path),
        "base_ref": base_ref,
        "target_ref": target_ref,
        "llm_provider": os.environ.get("LLM_PROVIDER", "bedrock"),
        "force_refresh": True,
    }
    print(f"POST {url}")
    print(f"  repo_path:  {payload['repo_path']}")
    print(f"  base_ref:   {base_ref}")
    print(f"  target_ref: {target_ref}")

    resp = requests.post(url, json=payload, timeout=300)
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
            subcategory=f.get("subcategory", ""),
            reviewer=f.get("reviewer", ""),
        )
        for f in findings
    ]


def print_section(title: str):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print('=' * 50)


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
    truths = load_ground_truth(fixtures_dir, args.repo_path)
    correctness_truths = [t for t in truths if t.category == "correctness"]
    security_truths = [t for t in truths if t.category == "security"]
    print(f"\nGround truth: {len(truths)} seeded defects "
          f"({len(correctness_truths)} correctness, {len(security_truths)} security)")

    try:
        review_data = run_review(args.repo_path, args.base_ref, args.target_ref)
    except requests.ConnectionError:
        print(f"\nERROR: Cannot connect to {API_BASE}. Is the Django server running?")
        sys.exit(1)
    except requests.HTTPError as exc:
        print(f"\nERROR: API returned {exc.response.status_code}: {exc.response.text}")
        sys.exit(1)

    review_status = review_data.get("status")
    findings_raw = review_data.get("findings", [])
    errors = review_data.get("errors", [])
    metadata = review_data.get("review_metadata", {})
    reviewer_latencies = metadata.get("reviewer_latencies", {})

    print(f"\nReview status: {review_status}")
    print(f"Total Combined Findings: {len(findings_raw)}")
    if errors:
        print(f"Errors:        {errors}")

    # Print latency data
    if reviewer_latencies:
        print(f"\n--- Reviewer Latencies ---")
        for k, v in reviewer_latencies.items():
            print(f"  {k}: {v}ms")

    # Separate LLM and Linter findings
    llm_findings = [f for f in findings_raw if f.get("source") != "linter"]
    linter_findings = [f for f in findings_raw if f.get("source") == "linter"]

    predictions = findings_to_predictions(llm_findings)

    # --- Overall LLM Metrics ---
    overall = calculate_metrics(truths, predictions)
    print_section("OVERALL LLM EVALUATION RESULTS")
    print(f"True Positives:  {overall.true_positives} / {len(truths)}")
    print(f"False Positives: {overall.false_positives}")
    print(f"False Negatives: {overall.false_negatives}")
    print(f"Precision:       {overall.precision:.4f}")
    print(f"Recall:          {overall.recall:.4f}")
    print(f"F1:              {overall.f1:.4f}")

    # --- Per-Category LLM Metrics ---
    by_category = calculate_metrics_by_category(truths, predictions)
    print_section("PER-CATEGORY LLM RESULTS")
    for cat, result in sorted(by_category.items()):
        cat_truths = [t for t in truths if t.category == cat]
        cat_preds = [p for p in predictions if p.category == cat]
        print(f"\n  [{cat.upper()}]")
        print(f"  TP={result.true_positives}/{len(cat_truths)}  FP={result.false_positives}  FN={result.false_negatives}")
        print(f"  Precision: {result.precision:.4f}  Recall: {result.recall:.4f}  F1: {result.f1:.4f}")

    # --- Per-Subcategory LLM Recall ---
    subcategory_recall = calculate_recall_by_subcategory(truths, predictions)
    print_section("PER-SUBCATEGORY LLM RECALL")
    for sub, recall in sorted(subcategory_recall.items()):
        bar = "✅" if recall >= 1.0 else ("⚠️ " if recall > 0 else "❌")
        print(f"  {bar} {sub:<25} recall={recall:.4f}")

    # --- Matched Pairs ---
    if overall.matched_pairs:
        print(f"\n--- Matched pairs (truth_id → pred_id) ---")
        for tid, pid in overall.matched_pairs:
            print(f"  {tid} → {pid}")
            
    # --- Linter Metrics ---
    print_section("DETERMINISTIC LINTER RESULTS")
    print(f"Linter Findings: {len(linter_findings)}")
    affected_files = len(set(f.get("file") for f in linter_findings))
    lint_rules = set(f.get("subcategory") for f in linter_findings)
    print(f"Affected Files:  {affected_files}")
    print(f"Rules Triggered: {', '.join(lint_rules) if lint_rules else 'None'}")

    # --- Write Output ---
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    usage_data = review_data.get("usage", {})
    reviewer_usages = review_data.get("reviewer_usage", [])
    
    # Print Usage Summary
    if usage_data:
        print_section("LLM USAGE METRICS")
        print(f"Total Tokens:    {usage_data.get('total_tokens')}")
        print(f"Latency:         {usage_data.get('total_latency_ms')} ms")
        print(f"Estimated Cost:  ${usage_data.get('total_estimated_cost')}")
        print(f"LLM Calls:       {usage_data.get('llm_calls')}")
        print(f"Provider:        {usage_data.get('provider')}")
        print(f"Models:          {', '.join(usage_data.get('models_used', []))}")

    output_data = {
        "review_id": review_data.get("id"),
        "repo_path": args.repo_path,
        "base_ref": args.base_ref,
        "target_ref": args.target_ref,
        "status": review_status,
        "usage": {
            "input_tokens": usage_data.get("total_input_tokens", 0),
            "output_tokens": usage_data.get("total_output_tokens", 0),
            "total_tokens": usage_data.get("total_tokens", 0),
            "latency_ms": usage_data.get("total_latency_ms", 0),
            "estimated_cost": usage_data.get("total_estimated_cost"),
            "provider": usage_data.get("provider", ""),
            "models_used": usage_data.get("models_used", []),
        },
        "reviewer_usages": reviewer_usages,
        "llm": {
            "seeded_defects_count": len(truths),
            "findings_count": len(llm_findings),
            "true_positives": overall.true_positives,
            "false_positives": overall.false_positives,
            "false_negatives": overall.false_negatives,
            "precision": overall.precision,
            "recall": overall.recall,
            "f1": overall.f1,
            "by_category": {
                cat: {
                    "true_positives": r.true_positives,
                    "false_positives": r.false_positives,
                    "false_negatives": r.false_negatives,
                    "precision": r.precision,
                    "recall": r.recall,
                    "f1": r.f1,
                }
                for cat, r in by_category.items()
            },
            "subcategory_recall": subcategory_recall,
            "matched_pairs": overall.matched_pairs,
        },
        "linter": {
            "finding_count": len(linter_findings),
            "affected_files": affected_files,
            "rules_triggered": list(lint_rules),
        },
        "combined": {
            "total_findings": len(findings_raw),
        },
        "reviewer_latencies": reviewer_latencies,
        "predictions": [
            {"id": p.id, "file": p.file, "line": p.line,
             "category": p.category, "confidence": p.confidence,
             "subcategory": p.subcategory, "reviewer": p.reviewer,
             "source": p.source if hasattr(p, 'source') else 'llm'}
            for p in predictions
        ],
        "errors": errors,
    }
    output_path.write_text(json.dumps(output_data, indent=2))
    print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
