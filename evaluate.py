#!/usr/bin/env python3
import os
import sys
import argparse
import asyncio
import statistics
import time

# Set up Django context to use ReviewOrchestrator
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from sentinel.services.review_orchestrator import ReviewOrchestrator

TEST_SUITE = [
    {"name": "auth-bypass", "repo": "test-repo/auth-bypass", "base": "HEAD~1", "target": "HEAD"},
    {"name": "multi-loop", "repo": "test-repo/multi-loop", "base": "HEAD~1", "target": "HEAD"},
    {"name": "seed_repo", "repo": "test-repo/seed_repo", "base": "HEAD~1", "target": "HEAD"},
    {"name": "single-js", "repo": "test-repo/single-js", "base": "HEAD~1", "target": "HEAD"},
    {"name": "breakableflask", "repo": "test-repo/breakableflask", "base": "b3297f7~1", "target": "b3297f7"}
]

async def run_evaluation(repo: str, base: str, target: str, runs: int, provider: str):
    print(f"\\n{'='*60}")
    print(f"EVALUATING: {repo} (Runs: {runs})")
    print(f"{'='*60}")
    
    metrics = {
        "input_tokens": [],
        "output_tokens": [],
        "total_tokens": [],
        "latency_ms": [],
        "mcp_calls": [],
        "findings": []
    }
    
    orchestrator = ReviewOrchestrator()
    
    for i in range(runs):
        print(f"\\n--- Run {i+1}/{runs} ---")
        try:
            start_time = time.monotonic()
            
            findings, errors, metadata, llm_usages = await orchestrator.run_review(
                review_id="eval-run",
                repo_path=os.path.abspath(repo),
                base_ref=base,
                target_ref=target,
                llm_provider=provider
            )
            
            # Print findings live
            for idx, finding in enumerate(findings, 1):
                f = finding.model_dump() if hasattr(finding, "model_dump") else finding
                print(f"[{idx}] {f.get('severity', 'UNKNOWN')} | {f.get('category', 'UNKNOWN')} | {f.get('file', '')}:{f.get('line', '')}")
                print(f"    Title: {f.get('title', '')}")
                print(f"    Fix: {f.get('suggested_fix', '')}")
            
            # Calculate tokens
            input_tokens = sum(usage.get("input_tokens", 0) for usage in llm_usages)
            output_tokens = sum(usage.get("output_tokens", 0) for usage in llm_usages)
            total_tokens = input_tokens + output_tokens
            latency_ms = metadata.get('critical_path_latency_ms', int((time.monotonic() - start_time) * 1000))
            mcp_calls = metadata.get('mcp_calls', 0)
            
            metrics["input_tokens"].append(input_tokens)
            metrics["output_tokens"].append(output_tokens)
            metrics["total_tokens"].append(total_tokens)
            metrics["latency_ms"].append(latency_ms)
            metrics["mcp_calls"].append(mcp_calls)
            metrics["findings"].append(len(findings))
            
            print(f"\\n[Run Metrics] Latency: {latency_ms}ms | Total Tokens: {total_tokens} | MCP: {mcp_calls} | Findings: {len(findings)}")
            
        except Exception as e:
            print(f"Run {i+1} encountered an exception: {e}")
            import traceback
            traceback.print_exc()

    print(f"\\n--- SUMMARY FOR {repo} ---")
    completed = len(metrics['input_tokens'])
    print(f"Runs completed: {completed}/{runs}")
    if completed > 0:
        print(f"Avg Input Tokens:  {statistics.mean(metrics['input_tokens']):.0f}")
        print(f"Avg Output Tokens: {statistics.mean(metrics['output_tokens']):.0f}")
        print(f"Avg Total Tokens:  {statistics.mean(metrics['total_tokens']):.0f}")
        print(f"Avg Latency (ms):  {statistics.mean(metrics['latency_ms']):.0f}")
        print(f"Avg MCP Calls:     {statistics.mean(metrics['mcp_calls']):.1f}")
        print(f"Avg Findings:      {statistics.mean(metrics['findings']):.1f}")
        if completed > 1:
            print(f"Stability (Findings StdDev): ±{statistics.stdev(metrics['findings']):.2f}")

async def main():
    parser = argparse.ArgumentParser(description="Unified evaluation script for CodeSentinel AI.")
    parser.add_argument("--repo", help="Path to local git repo (if testing a single repo)")
    parser.add_argument("--base", help="Base commit/branch (required if --repo is used)")
    parser.add_argument("--target", help="Target commit/branch (required if --repo is used)")
    parser.add_argument("--all", action="store_true", help="Run evaluation suite on all predefined test repos")
    parser.add_argument("--provider", default="bedrock", choices=["openai", "bedrock"], help="LLM Provider")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to run the review")
    
    args = parser.parse_args()
    
    if args.all:
        for suite in TEST_SUITE:
            await run_evaluation(suite["repo"], suite["base"], suite["target"], args.runs, args.provider)
    elif args.repo and args.base and args.target:
        await run_evaluation(args.repo, args.base, args.target, args.runs, args.provider)
    else:
        print("Error: You must provide either --all OR --repo, --base, and --target.")
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())
