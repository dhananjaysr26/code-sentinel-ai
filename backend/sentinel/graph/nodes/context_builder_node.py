import logging
import time
from pathlib import Path
from django.conf import settings
from sentinel.graph.state import ReviewState
from sentinel.mcp.client import StdioMCPClient
from sentinel.context.builder import ContextBuilder
from sentinel.schemas.context import ContextBudget
from sentinel.graph.context_planner import run_context_planner

logger = logging.getLogger(__name__)

async def build_context_node(state: ReviewState) -> dict:
    start = time.monotonic()
    errors = list(state.get("errors", []))
    metadata = dict(state.get("metadata", {}))
    diff_hunks = state.get("diff_hunks", [])
    raw_diff = state.get("raw_diff", "")
    changed_files = [f["path"] if isinstance(f, dict) else f.path for f in state.get("changed_files", [])]

    # Run Deterministic Context Planner
    planned_evidence = run_context_planner(raw_diff, changed_files)
    evidence_package = planned_evidence.model_dump()

    if not diff_hunks:
        logger.info("No diff hunks; skipping context building")
        metadata.setdefault("node_durations", {})["build_context"] = 0.0
        return {
            "evidence_package": evidence_package,
            "context_blocks": [], 
            "errors": errors, 
            "metadata": metadata
        }

    server_script = str(Path(settings.MCP_SERVER_SCRIPT).resolve())
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

    return {
        "evidence_package": evidence_package,
        "context_blocks": context_blocks,
        "errors": errors,
        "metadata": metadata,
    }
