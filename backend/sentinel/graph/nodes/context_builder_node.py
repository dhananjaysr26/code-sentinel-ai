"""
LangGraph node: build_context

Responsibility:
  - Create an MCP client connected to the MCP server.
  - For each diff hunk, retrieve surrounding source context via MCP.
  - Apply token budget.
  - Return ContextBlock list.

This node demonstrates the LangGraph → MCP client → MCP server → repo data path.
"""
import logging
import time
from pathlib import Path

from django.conf import settings

from sentinel.graph.state import ReviewState
from sentinel.mcp.client import StdioMCPClient
from sentinel.context.builder import ContextBuilder
from sentinel.schemas.context import ContextBudget

logger = logging.getLogger(__name__)


async def build_context_node(state: ReviewState) -> dict:
    """Build context blocks for all diff hunks via MCP.
    
    Input state fields: diff_hunks, repo_path, metadata
    Output state fields: context_blocks, errors, metadata
    """
    start = time.monotonic()
    errors = list(state.get("errors", []))
    metadata = dict(state.get("metadata", {}))
    diff_hunks = state.get("diff_hunks", [])

    if not diff_hunks:
        logger.info("No diff hunks; skipping context building")
        metadata.setdefault("node_durations", {})["build_context"] = 0.0
        return {"context_blocks": [], "errors": errors, "metadata": metadata}

    # Resolve the MCP server script path
    server_script = str(Path(settings.MCP_SERVER_SCRIPT).resolve())
    logger.debug("Using MCP server: %s", server_script)

    budget = ContextBudget(
        max_tokens=settings.CONTEXT_MAX_TOKENS,
        window_lines=settings.CONTEXT_WINDOW_LINES,
    )

    mcp_client = StdioMCPClient(server_script=server_script)
    builder = ContextBuilder(mcp_client=mcp_client, budget=budget)

    try:
        context_blocks = await builder.build(
            hunks=diff_hunks,
            repo_path=state["repo_path"],
        )
    except Exception as exc:
        msg = f"Context building failed: {exc}"
        logger.error(msg)
        errors.append(msg)
        context_blocks = []

    duration = time.monotonic() - start
    metadata.setdefault("node_durations", {})["build_context"] = round(duration, 3)

    logger.info(
        "[%s] build_context complete: %d blocks in %.2fs",
        metadata.get("review_id", "?"),
        len(context_blocks),
        duration,
    )

    return {
        "context_blocks": context_blocks,
        "errors": errors,
        "metadata": metadata,
    }
