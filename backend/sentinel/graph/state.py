"""
LangGraph shared state for the review workflow.

ReviewState is a TypedDict because LangGraph requires a TypedDict or
Annotated TypedDict for state. All fields are Optional to allow partial
population as the graph progresses.

State flows through nodes:
  parse_diff → build_context → correctness_review → validate_findings
Each node reads what it needs and returns a dict of the fields it updates.
"""
from typing import TypedDict, Optional

from sentinel.schemas.diff import ChangedFile, DiffHunk
from sentinel.schemas.context import ContextBlock
from sentinel.schemas.findings import Finding


class ReviewState(TypedDict):
    # ── Input (provided by ReviewOrchestrator before graph starts) ───────────
    repo_path: str
    base_ref: str
    target_ref: str
    llm_provider: str  # 'openai' or 'bedrock'

    # ── Populated by parse_diff node ─────────────────────────────────────────
    raw_diff: str
    changed_files: list[ChangedFile]
    diff_hunks: list[DiffHunk]   # flat list across all files

    # ── Populated by build_context node ──────────────────────────────────────
    context_blocks: list[ContextBlock]

    # ── Populated by correctness_review node ─────────────────────────────────
    raw_findings: list[dict]     # raw model output before schema validation

    # ── Populated by validate_findings node ──────────────────────────────────
    findings: list[Finding]

    # ── Bookkeeping (cumulative across nodes) ─────────────────────────────────
    errors: list[str]
    metadata: dict               # review_id, start_time, node_durations, etc.
