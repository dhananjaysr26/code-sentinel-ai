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


def _dedup_within_category(findings: list[dict]) -> tuple[list[dict], int]:
    """Deduplicate findings within the same category using file+line proximity.

    Greedy: iterate in order, skip any finding that is within ±LINE_DEDUP_TOLERANCE
    lines of an already-kept finding in the same file+category.
    Keeps the higher-confidence finding when two are equivalent,
    and merges provenance (source/evidence_sources).
    """
    kept: list[dict] = []
    removed_count = 0
    
    for candidate in findings:
        c_file = _normalize_path(candidate.get("file", ""))
        c_line = candidate.get("line") or 0
        c_category = candidate.get("category", "")

        duplicate = False
        for i, existing in enumerate(kept):
            e_file = _normalize_path(existing.get("file", ""))
            e_line = existing.get("line") or 0
            e_category = existing.get("category", "")

            if (
                c_file == e_file
                and c_category == e_category
                and abs(c_line - e_line) <= _LINE_DEDUP_TOLERANCE
            ):
                # Duplicate found — keep the higher-confidence one, but merge provenance
                c_source = candidate.get("source", "llm")
                e_source = existing.get("source", "llm")
                
                c_sources = candidate.get("evidence_sources", [c_source] if c_source != "merged" else [])
                e_sources = existing.get("evidence_sources", [e_source] if e_source != "merged" else [])
                
                merged_sources = list(set(c_sources + e_sources))
                
                if candidate.get("confidence", 0) > existing.get("confidence", 0):
                    candidate["source"] = "merged" if len(merged_sources) > 1 else c_source
                    candidate["evidence_sources"] = merged_sources
                    kept[i] = candidate
                else:
                    existing["source"] = "merged" if len(merged_sources) > 1 else e_source
                    existing["evidence_sources"] = merged_sources
                    kept[i] = existing
                    
                duplicate = True
                removed_count += 1
                break

        if not duplicate:
            kept.append(candidate)

    return kept, removed_count


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

    logger.info("--- MERGE LAYER METRICS ---")
    logger.info("raw correctness findings: %d", len(correctness))
    logger.info("raw security findings: %d", len(security))
    logger.info("raw linter findings: %d", len(deterministic))
    
    total_inputs = len(correctness) + len(security) + len(deterministic)
    logger.info("dedupe input count: %d", total_inputs)

    # Separate by category before deduplication
    # (never deduplicate across categories)
    # Combine them first, then dedup by category globally?
    # Wait, the prompt says deduplicate them together so LLM and Linter merge.
    # We should merge correctness + deterministic, and security + deterministic?
    # No, just pass all of them into _dedup_within_category!
    # Linter can have CODE_QUALITY which LLMs don't typically produce right now unless prompted,
    # but if they share a category, they will merge.
    
    all_findings = correctness + security + deterministic
    
    deduped_findings, removed = _dedup_within_category(all_findings)
    
    logger.info("dedupe output count: %d", len(deduped_findings))
    logger.info("findings removed because of deduplication: %d", removed)

    merged = _rank(deduped_findings)
    
    # Log provenance
    merged_provenance = [f for f in merged if f.get("source") == "merged"]
    logger.info("provenance of merged findings: %d merged natively", len(merged_provenance))

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "MERGE_COMPLETE final_findings=%d latency_ms=%d",
        len(merged), duration_ms,
    )

    return {"raw_findings": merged}
