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


async def validate_findings_node(state: ReviewState) -> dict:
    """Validate and deduplicate raw findings.
    
    Input state fields: raw_findings, metadata
    Output state fields: findings, errors, metadata
    """
    start = time.monotonic()
    errors = list(state.get("errors", []))
    metadata = dict(state.get("metadata", {}))
    raw_findings = state.get("raw_findings", [])

    valid_findings: list[Finding] = []

    for i, raw in enumerate(raw_findings):
        try:
            finding = Finding(**raw)
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
