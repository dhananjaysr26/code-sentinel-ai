import re

with open("backend/sentinel/graph/nodes/context_builder_node.py", "r") as f:
    content = f.read()

replacement = """
from sentinel.graph.context_planner import run_context_planner

async def build_context_node(state: ReviewState) -> dict:
    start = time.monotonic()
    errors = list(state.get("errors", []))
    metadata = dict(state.get("metadata", {}))
    diff_hunks = state.get("diff_hunks", [])
    raw_diff = state.get("raw_diff", "")
    changed_files = [f["path"] for f in state.get("changed_files", [])]

    if not diff_hunks:
        logger.info("No diff hunks; skipping context building")
        metadata.setdefault("node_durations", {})["build_context"] = 0.0
        return {"context_blocks": [], "errors": errors, "metadata": metadata}

    # Run Deterministic Context Planner
    planned_evidence = run_context_planner(raw_diff, changed_files)

    # Resolve the MCP server script path
"""

content = re.sub(r'async def build_context_node.*?# Resolve the MCP server script path', replacement, content, flags=re.DOTALL)
content = content.replace('return {', 'return {\n        "evidence_package": planned_evidence.model_dump(),')

with open("backend/sentinel/graph/nodes/context_builder_node.py", "w") as f:
    f.write(content)
