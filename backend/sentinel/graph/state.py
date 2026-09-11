"""
LangGraph shared state for the review workflow.

ReviewState is a TypedDict because LangGraph requires a TypedDict or
Annotated TypedDict for state.

Phase 2: correctness + security reviewers run in PARALLEL.
Any state key written by more than one parallel node needs an Annotated
reducer so LangGraph knows how to merge concurrent writes.

Reducer strategy:
  - correctness_raw_findings: replace (only one writer)
  - security_raw_findings:    replace (only one writer)
  - errors:                   append — both reviewers may write errors
  - security_errors:          append — only security writes, but safe
  - reviewer_latencies:       merge dicts — both reviewers write their own key
  - raw_findings:             replace — only merge node writes
  - findings:                 replace — only validate node writes

State flows through nodes:
  parse_diff → build_context → [correctness_review ‖ security_review]
             → merge_findings → validate_findings
"""
from typing import Annotated, TypedDict, Optional
from operator import add

from sentinel.schemas.diff import ChangedFile, DiffHunk
from sentinel.schemas.context import ContextBlock
from sentinel.schemas.findings import Finding


def _merge_dicts(a: dict, b: dict) -> dict:
    """Reducer that merges two dicts (later values win for same keys)."""
    return {**a, **b}


def _replace(a, b):
    """Reducer that returns the latest value (standard replace semantics)."""
    return b


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

    # ── Populated by correctness_review node (parallel) ──────────────────────
    correctness_raw_findings: list[dict]

    # ── Populated by security_review node (parallel) ─────────────────────────
    security_raw_findings: list[dict]
    
    # ── Populated by deterministic_checks node (parallel) ──────────────────────
    deterministic_raw_findings: list[dict]

    # ── Written by BOTH parallel reviewers — needs append reducer ────────────
    errors: Annotated[list[str], add]
    security_errors: Annotated[list[str], add]
    llm_usages: Annotated[list[dict], add]

    # ── Written by BOTH parallel reviewers — needs merge-dict reducer ─────────
    reviewer_latencies: Annotated[dict, _merge_dicts]

    # ── Populated by merge_findings node ────────────────────────────────────
    raw_findings: list[dict]     # merged + ranked from both reviewers

    # ── Populated by validate_findings node ──────────────────────────────────
    findings: list[Finding]

    # ── Bookkeeping ───────────────────────────────────────────────────────────
    metadata: dict               # review_id, start_time, node_durations, etc.
