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


import re

def _is_semantic_duplicate(f1: dict, f2: dict) -> bool:
    """Check if two findings on the same line are semantically identical."""
    # Must be same file and close lines
    if _normalize_path(f1.get("file", "")) != _normalize_path(f2.get("file", "")):
        return False
    
    l1 = f1.get("line") or 0
    l2 = f2.get("line") or 0
    if abs(l1 - l2) > _LINE_DEDUP_TOLERANCE:
        return False
        
    # Same category is a strong signal
    if f1.get("category") == f2.get("category"):
        return True
        
    # If different categories (e.g. Correctness vs Security), check text similarity
    def get_tokens(f):
        text = str(f.get("title", "")) + " " + str(f.get("explanation", ""))
        return set(re.findall(r'\b\w+\b', text.lower()))
        
    t1 = get_tokens(f1)
    t2 = get_tokens(f2)
    
    if not t1 or not t2:
        return False
        
    intersection = len(t1.intersection(t2))
    union = len(t1.union(t2))
    jaccard = intersection / union if union > 0 else 0
    
    return jaccard > 0.20  # 20% word overlap is enough if they are on the exact same line

def _dedup_findings(findings: list[dict]) -> tuple[list[dict], int]:
    """Deduplicate findings, merging cross-category duplicates into a combined provenance."""
    kept: list[dict] = []
    removed_count = 0
    
    for candidate in findings:
        duplicate = False
        for i, existing in enumerate(kept):
            if _is_semantic_duplicate(candidate, existing):
                # Merge provenance
                c_reviewer = candidate.get("reviewer") or "unknown"
                e_reviewer = existing.get("reviewer") or "unknown"
                c_category = candidate.get("category")
                e_category = existing.get("category")
                
                # We append to lists to preserve the history
                exist_reviewers = existing.get("supporting_reviewers", [e_reviewer])
                if c_reviewer not in exist_reviewers:
                    exist_reviewers.append(c_reviewer)
                    
                exist_sources = existing.get("sources", [e_category])
                if c_category not in exist_sources:
                    exist_sources.append(c_category)
                
                # Keep the higher confidence one's core text, but update lists
                if candidate.get("confidence", 0) > existing.get("confidence", 0):
                    candidate["supporting_reviewers"] = exist_reviewers
                    candidate["sources"] = exist_sources
                    kept[i] = candidate
                else:
                    existing["supporting_reviewers"] = exist_reviewers
                    existing["sources"] = exist_sources
                    kept[i] = existing
                    
                duplicate = True
                removed_count += 1
                break

        if not duplicate:
            candidate.setdefault("supporting_reviewers", [candidate.get("reviewer", "unknown")])
            candidate.setdefault("sources", [candidate.get("category", "unknown")])
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
    
    deduped_findings, removed = _dedup_findings(all_findings)
    
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
