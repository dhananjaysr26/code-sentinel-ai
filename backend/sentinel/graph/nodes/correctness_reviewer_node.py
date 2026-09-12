"""
Correctness Reviewer LangGraph node — iterative MCP-enabled version.

Replaces the single invoke_structured() call with run_iterative_reviewer(),
which supports an LLM → MCP tool → LLM loop bounded by hard limits.

Runs in PARALLEL with security_review_node after build_context.
"""
import logging
import time
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from langsmith import traceable

from sentinel.mcp.client import StdioMCPClient
from sentinel.graph.nodes.iterative_reviewer import run_iterative_reviewer

logger = logging.getLogger(__name__)


@traceable(name="correctness_reviewer_node")
async def correctness_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes the diff and context to find correctness bugs.

    Uses the iterative MCP loop: the LLM may call read_file / find_references
    to retrieve missing context before returning its final findings.
    """
    start_time = time.monotonic()
    review_id = state.get("metadata", {}).get("review_id", "?")
    blocks = state.get("context_blocks", [])

    logger.info(
        "REVIEWER_START reviewer=correctness review_id=%s context_blocks=%d",
        review_id, len(blocks),
    )

    if not blocks:
        logger.info("correctness_review_node: no context blocks, skipping")
        return {"correctness_raw_findings": []}

    provider = state.get("llm_provider", settings.LLM_PROVIDER).lower()
    server_script = str(Path(settings.MCP_SERVER_SCRIPT).resolve())
    mcp_client = StdioMCPClient(server_script=server_script)

    result = await run_iterative_reviewer(
        specialist="correctness",
        state=state,
        provider=provider,
        repo_path=state["repo_path"],
        mcp_client=mcp_client,
    )

    latency_ms = int((time.monotonic() - start_time) * 1000)
    findings = result.get("correctness_raw_findings", [])
    loop_summary = result.get("reviewer_latencies", {}).get("correctness_loop", {})

    logger.info(
        "REVIEWER_COMPLETE reviewer=correctness findings=%d latency_ms=%d "
        "llm_calls=%d tool_calls=%d stop_reason=%s",
        len(findings),
        latency_ms,
        loop_summary.get("llm_call_count", "?"),
        loop_summary.get("tool_call_count", "?"),
        loop_summary.get("stop_reason", "?"),
    )

    return result
