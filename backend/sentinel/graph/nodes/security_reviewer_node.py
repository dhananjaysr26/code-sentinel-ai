"""
Security Reviewer LangGraph node — iterative MCP-enabled version.

Replaces the single invoke_structured() call with run_iterative_reviewer(),
which supports an LLM → MCP tool → LLM loop bounded by hard limits.

Focus areas:
- Injection vulnerabilities (SQL, command, template)
- Authentication / authorization bypass
- Hardcoded secrets and credential exposure
- Missing input validation on user-controlled data
- Unsafe file handling

Runs in PARALLEL with correctness_review_node after build_context.
One failing does not affect the other.
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


@traceable(name="security_reviewer_node")
async def security_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes the diff and context to find security vulnerabilities.

    Uses the iterative MCP loop: the LLM may call read_file / find_references
    to retrieve missing context (e.g. policy.py definitions) before returning
    its final findings.

    Authorization-related changes trigger the policy-inspection path because
    the system prompt explicitly instructs the LLM to use read_file when a
    policy key, role identifier, or permission string is opaque.
    """
    start_time = time.monotonic()
    review_id = state.get("metadata", {}).get("review_id", "?")
    blocks = state.get("context_blocks", [])

    logger.info(
        "REVIEWER_START reviewer=security review_id=%s context_blocks=%d",
        review_id, len(blocks),
    )

    if not blocks:
        logger.info("security_review_node: no context blocks, skipping")
        return {"security_raw_findings": []}

    provider = state.get("llm_provider", settings.LLM_PROVIDER).lower()
    server_script = str(Path(settings.MCP_SERVER_SCRIPT).resolve())
    mcp_client = StdioMCPClient(server_script=server_script)

    result = await run_iterative_reviewer(
        specialist="security",
        state=state,
        provider=provider,
        repo_path=state["repo_path"],
        mcp_client=mcp_client,
    )

    latency_ms = int((time.monotonic() - start_time) * 1000)
    findings = result.get("security_raw_findings", [])
    loop_summary = result.get("reviewer_latencies", {}).get("security_loop", {})

    logger.info(
        "REVIEWER_COMPLETE reviewer=security findings=%d latency_ms=%d "
        "llm_calls=%d tool_calls=%d stop_reason=%s",
        len(findings),
        latency_ms,
        loop_summary.get("llm_call_count", "?"),
        loop_summary.get("tool_call_count", "?"),
        loop_summary.get("stop_reason", "?"),
    )

    return result
