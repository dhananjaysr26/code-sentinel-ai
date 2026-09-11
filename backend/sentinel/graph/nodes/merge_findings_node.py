"""
LangGraph node: merge_findings

Responsibility:
  - Combine correctness_raw_findings + security_raw_findings from parallel branches.
  - Deduplicate findings within the same category/file/line.
  - Rank by severity (CRITICAL > HIGH > MEDIUM > LOW), then confidence (desc).

Deduplication strategy (MVP):
  - Normalize file path (strip leading ./ or src/).
  - Same file + same line (within ±3) + same category → deduplicate.
  - Keep the finding with higher confidence.
  - NEVER deduplicate across different categories:
    a correctness NoneType error and a security injection at the same line
    are genuinely distinct findings that should both be reported.

Trade-off documented:
  - ±3 line tolerance can cause false merges when two distinct bugs of the
    same category are very close together. This is acceptable for MVP.
  - A future improvement would use semantic similarity (embeddings) to
    determine whether two same-location findings describe the same root cause.

Output → raw_findings (consumed by validate_findings_node)
"""
import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_LINE_DEDUP_TOLERANCE = 3


def _normalize_path(path: str) -> str:
    """Strip leading ./, /, or src/ for path comparison."""
    path = path.lstrip("./").lstrip("/")
    return path


def _dedup_within_category(findings: list[dict]) -> list[dict]:
    """Deduplicate findings within the same category using file+line proximity.

    Greedy: iterate in order, skip any finding that is within ±LINE_DEDUP_TOLERANCE
    lines of an already-kept finding in the same file+category+source+subcategory.
    Keeps the higher-confidence finding when two are equivalent.
    """
    kept: list[dict] = []
    for candidate in findings:
        c_file = _normalize_path(candidate.get("file", ""))
        c_line = candidate.get("line") or 0
        c_category = candidate.get("category", "")
        c_source = candidate.get("source", "")
        c_subcategory = candidate.get("subcategory", "")

        duplicate = False
        for i, existing in enumerate(kept):
            e_file = _normalize_path(existing.get("file", ""))
            e_line = existing.get("line") or 0
            e_category = existing.get("category", "")
            e_source = existing.get("source", "")
            e_subcategory = existing.get("subcategory", "")

            if (
                c_file == e_file
                and c_category == e_category
                and c_source == e_source
                and c_subcategory == e_subcategory
                and abs(c_line - e_line) <= _LINE_DEDUP_TOLERANCE
            ):
                # Duplicate found — keep the higher-confidence one
                if candidate.get("confidence", 0) > existing.get("confidence", 0):
                    kept[i] = candidate
                duplicate = True
                break

        if not duplicate:
            kept.append(candidate)

    return kept


def _rank(findings: list[dict]) -> list[dict]:
    """Sort by severity rank (critical first), then confidence descending."""
    return sorted(
        findings,
        key=lambda f: (
            _SEVERITY_RANK.get(f.get("severity", "low").lower(), 99),
            -f.get("confidence", 0.0),
        ),
    )


async def merge_findings_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Fan-in node: merge findings from both parallel reviewers and deterministic checks.

    Input:  correctness_raw_findings, security_raw_findings, deterministic_raw_findings
    Output: raw_findings (merged, deduped, ranked)
    """
    start = time.monotonic()

    correctness = list(state.get("correctness_raw_findings") or [])
    security = list(state.get("security_raw_findings") or [])
    deterministic = list(state.get("deterministic_raw_findings") or [])

    logger.info(
        "MERGE_START correctness_count=%d security_count=%d deterministic_count=%d",
        len(correctness), len(security), len(deterministic)
    )

    # Separate by category before deduplication
    # (never deduplicate across categories)
    deduped_correctness = _dedup_within_category(correctness)
    deduped_security = _dedup_within_category(security)
    deduped_deterministic = _dedup_within_category(deterministic)

    # Combine and rank globally
    merged = _rank(deduped_correctness + deduped_security + deduped_deterministic)

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "MERGE_COMPLETE llm_findings=%d deterministic_findings=%d final_findings=%d latency_ms=%d",
        len(deduped_correctness) + len(deduped_security), len(deduped_deterministic), len(merged), duration_ms,
    )

    return {"raw_findings": merged}
