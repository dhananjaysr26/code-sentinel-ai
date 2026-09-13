"""
LangGraph node: validate_findings

Responsibility:
  - Validate each raw_finding dict against the Finding Pydantic schema.
  - Deduplicate valid findings via FindingDeduplicator.
  - Record validation errors without crashing the pipeline.

This is the Pydantic schema gate between the LLM output and the frontend.
The frontend never receives raw model text.
"""
import logging
import time

from pydantic import ValidationError

from sentinel.graph.state import ReviewState
from sentinel.schemas.findings import Finding
from sentinel.services.deduplicator import FindingDeduplicator

logger = logging.getLogger(__name__)

_deduplicator = FindingDeduplicator()


def _is_line_in_diff(file_path: str, line_num: int, diff_hunks: list) -> bool:
    if not line_num:
        return False
    
    # Allow a small tolerance for off-by-one LLM hallucination
    allowed_lines = set()
    for hunk in diff_hunks:
        if hunk.file_path == file_path:
            allowed_lines.update(hunk.changed_line_numbers)
            
    if not allowed_lines:
        return False
        
    return line_num in allowed_lines or (line_num - 1) in allowed_lines or (line_num + 1) in allowed_lines


async def validate_findings_node(state: ReviewState) -> dict:
    """Validate and deduplicate raw findings.
    
    Input state fields: raw_findings, metadata, diff_hunks
    Output state fields: findings, errors, metadata
    """
    start = time.monotonic()
    errors = list(state.get("errors", []))
    metadata = dict(state.get("metadata", {}))
    raw_findings = state.get("raw_findings", [])
    diff_hunks = state.get("diff_hunks", [])

    valid_findings: list[Finding] = []

    for i, raw in enumerate(raw_findings):
        try:
            # 1. Pydantic schema validation
            finding = Finding(**raw)
            
            # 2. Line Anchor Validation
            if finding.line is None:
                msg = f"Finding '{finding.title}' rejected: Null line_start is not allowed."
                logger.warning(msg)
                errors.append(msg)
                continue
                
            if not _is_line_in_diff(finding.file, finding.line, diff_hunks):
                msg = f"Finding '{finding.title}' in {finding.file}:{finding.line} is not within the changed lines of the diff."
                logger.warning(msg)
                errors.append(msg)
                # Keep it but mark it unanchored by setting line to 0, or just let it be.
                # The user says "reject or mark unanchored". We'll keep it as unanchored for now (line=0)
                # wait, the Pydantic schema allows Optional[int]. Let's set it to None.
                # Wait, "Reject null line_start." "Never return null for line_start".
                # Okay, if it's out of bounds, we'll REJECT IT. This enforces strict anchoring.
                continue
                
            valid_findings.append(finding)
        except ValidationError as exc:
            msg = f"Finding #{i} failed schema validation: {exc.error_count()} error(s)"
            logger.warning("%s — raw: %r", msg, raw)
            errors.append(msg)

    if len(valid_findings) < len(raw_findings):
        logger.warning(
            "Dropped %d invalid findings (kept %d valid)",
            len(raw_findings) - len(valid_findings),
            len(valid_findings),
        )

    deduplicated = _deduplicator.deduplicate(valid_findings)

    duration = time.monotonic() - start
    metadata.setdefault("node_durations", {})["validate_findings"] = round(duration, 3)

    logger.info(
        "[%s] validate_findings complete: %d findings (after dedup) in %.2fs",
        metadata.get("review_id", "?"),
        len(deduplicated),
        duration,
    )

    return {
        "findings": deduplicated,
        "errors": errors,
        "metadata": metadata,
    }
