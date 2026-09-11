#!/usr/bin/env python3
"""
Stability test: run the same review N times and record variance.

Usage:
    python evals/stability_test.py [--repo-path evals/seed_repo] [--runs 3]

Records per run:
  - Finding count
  - Per-finding: file, line, title, severity, confidence
  - Latency

Output: evals/results/stability_results.json

This prepares the project for the assignment requirement of measuring
nondeterminism in LLM-based review systems.
"""
import argparse
import json
import time
import os
import sys
from pathlib import Path

import requests

_EVALS_DIR = Path(__file__).parent
_PROJECT_ROOT = _EVALS_DIR.parent
API_BASE = os.environ.get("CODESENTINEL_API", "http://localhost:8000")
DEFAULT_REPO = str(_PROJECT_ROOT.parent / "seed_repo")


def run_review(repo_path: str, base_ref: str, target_ref: str) -> tuple[dict, float]:
    start = time.monotonic()
    resp = requests.post(
        f"{API_BASE}/api/reviews/",
        json={
            "repo_path": str(Path(repo_path).resolve()),
            "base_ref": base_ref,
            "target_ref": target_ref,
            "llm_provider": "bedrock",
        },
        timeout=180,
    )
    latency = time.monotonic() - start
    resp.raise_for_status()
    return resp.json(), latency


def summarize_findings(findings: list[dict]) -> list[dict]:
    return [
        {
            "file": f["file"],
            "line": f.get("line"),
            "title": f["title"],
            "severity": f["severity"],
            "confidence": f["confidence"],
        }
        for f in findings
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Stability test for CodeSentinel AI")
    parser.add_argument("--repo-path", default=DEFAULT_REPO)
    parser.add_argument("--base-ref", default="HEAD~1")
    parser.add_argument("--target-ref", default="HEAD")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--output",
        default=str(_EVALS_DIR / "results" / "stability_results.json"),
    )
    args = parser.parse_args()

    print(f"Stability test: {args.runs} runs against {args.repo_path}")
    results = []

    for i in range(1, args.runs + 1):
        print(f"\nRun {i}/{args.runs}...", end=" ", flush=True)
        try:
            data, latency = run_review(args.repo_path, args.base_ref, args.target_ref)
            findings = data.get("findings", [])
            print(f"{len(findings)} findings in {latency:.1f}s")
            results.append({
                "run": i,
                "finding_count": len(findings),
                "latency_seconds": round(latency, 2),
                "status": data.get("status"),
                "findings": summarize_findings(findings),
            })
        except Exception as exc:
            print(f"FAILED: {exc}")
            results.append({"run": i, "error": str(exc)})

    # Summary statistics
    successful = [r for r in results if "error" not in r]
    counts = [r["finding_count"] for r in successful]
    latencies = [r["latency_seconds"] for r in successful]

    summary: dict = {
        "total_runs": args.runs,
        "successful_runs": len(successful),
    }
    if counts:
        summary.update({
            "min_findings": min(counts),
            "max_findings": max(counts),
            "avg_findings": round(sum(counts) / len(counts), 2),
            "finding_count_variance": (
                round(max(counts) - min(counts), 2)
            ),
            "min_latency_s": min(latencies),
            "max_latency_s": max(latencies),
            "avg_latency_s": round(sum(latencies) / len(latencies), 2),
        })

    output = {
        "repo_path": args.repo_path,
        "base_ref": args.base_ref,
        "target_ref": args.target_ref,
        "runs": results,
        "summary": summary,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))

    print("\n=== STABILITY SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nResults written to: {output_path}")


if __name__ == "__main__":
    main()
