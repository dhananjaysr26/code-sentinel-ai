#!/usr/bin/env python3
"""
CLI tool to trigger a CodeSentinel AI review on any repository.

Usage:
  python review.py --repo /path/to/repo --base HEAD~1 --target HEAD --provider openai
"""
import argparse
import time
import requests
import sys

API_BASE = "http://localhost:8000"

def main():
    p = argparse.ArgumentParser(description="Trigger CodeSentinel AI Review")
    p.add_argument("--repo", required=True, help="Path to the git repository")
    p.add_argument("--base", default="HEAD~1", help="Base git ref")
    p.add_argument("--target", default="HEAD", help="Target git ref")
    p.add_argument("--provider", default="bedrock", choices=["openai", "bedrock"], help="LLM provider")
    args = p.parse_args()

    url = f"{API_BASE}/api/reviews/"
    payload = {
        "repo_path": args.repo,
        "base_ref": args.base,
        "target_ref": args.target,
        "llm_provider": args.provider,
        "force_refresh": True,
    }

    print("=" * 60)
    print(f"Triggering Review: {args.repo}")
    print(f"Diff: {args.base} -> {args.target}")
    print(f"Provider: {args.provider}")
    print("=" * 60)

    try:
        response = requests.post(url, json=payload, timeout=300)
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to Django backend. Is it running on localhost:8000?")
        sys.exit(1)
    except requests.exceptions.ReadTimeout:
        print("ERROR: Request timed out after 5 minutes.")
        sys.exit(1)

    if response.status_code not in (200, 500):
        print(f"ERROR: API returned {response.status_code}: {response.text}")
        sys.exit(1)

    data = response.json()
    status_msg = data.get("status")
    
    if status_msg == "failed":
        print("\nReview failed:")
        for err in data.get("errors", []):
            print(f" - {err}")
        sys.exit(1)

    print("\n\n" + "=" * 60)
    print("EXECUTION TIMELINE")
    print("=" * 60)
    
    metadata = data.get("review_metadata", {})
    timeline = metadata.get("timeline", [])
    
    if not timeline:
        print("No timeline data available.")
    else:
        for ev in timeline:
            node = ev.get("node", "System").upper()
            event = ev.get("event", "Event")
            details = ev.get("details", "")
            latency = ev.get("latency_ms", 0)
            tokens = ev.get("tokens", 0)
            cache = " [cache_hit=true]" if ev.get("cache_hit") else (" [cache_hit=false]" if event == "tool_call" else "")
            
            token_str = f" [{tokens} tokens]" if tokens > 0 else ""
            print(f"[{node}] {event} -> {details} ({latency}ms){token_str}{cache}")

    print("\n" + "=" * 60)
    print("REVIEW SUMMARY")
    print("=" * 60)
    
    usage = data.get("usage", {})
    if usage:
        print(f"LLM calls: {usage.get('llm_calls', 0)}")
        print(f"MCP calls: {usage.get('mcp_calls', 0)}")
        print(f"Unique MCP calls: {usage.get('unique_mcp_calls', 0)}")
        print(f"Duplicate MCP calls: {usage.get('duplicate_mcp_calls', 0)}")
        print(f"Agent iterations: {usage.get('agent_iterations', 0)}")
        print(f"LangGraph node executions: {usage.get('langgraph_node_executions', 0)}")
        print(f"Retries: {usage.get('retry_count', 0)}")
        print(f"Fallbacks: {usage.get('fallback_count', 0)}")
        print(f"Timeouts: {usage.get('timeout_count', 0)}")
        print(f"Input tokens: {usage.get('total_input_tokens', 0)}")
        print(f"Output tokens: {usage.get('total_output_tokens', 0)}")
        print(f"Total tokens: {usage.get('total_tokens', 0)}")
        print(f"LLM latency: {usage.get('llm_latency_ms', 0)}ms")
        print(f"MCP latency: {usage.get('mcp_latency_ms', 0)}ms")
        print(f"Wall-clock latency: {usage.get('total_latency_ms', 0)}ms")
    
    findings = data.get("findings", [])
    print(f"Findings: {len(findings)}\n")
    
    for i, f in enumerate(findings, 1):
        print(f"[{i}] {f.get('severity', 'UNKNOWN').upper()} | {f.get('category')} | {f.get('file')}:{f.get('line')}")
        print(f"    Title: {f.get('title')}")
        print(f"    Explanation: {f.get('explanation')}")
        if f.get('suggested_fix'):
            print(f"    Fix: {f.get('suggested_fix')}")
        print("-" * 60)

if __name__ == "__main__":
    main()
