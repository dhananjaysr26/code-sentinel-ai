"""
Finding deduplicator.

The MVP has one reviewer, so duplication is rare. This module provides
the extension point for merging findings from multiple future reviewers
(correctness + security + linter).

Deduplication key: (file, line, normalized_title)
Policy: keep the finding with highest confidence when duplicates exist.
"""
import logging
from sentinel.schemas.findings import Finding, Severity

logger = logging.getLogger(__name__)

# Severity ordering for sort (higher = more severe)
_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}


class FindingDeduplicator:
    """Removes duplicate findings and sorts by severity/confidence.
    
    Extension point: future multi-reviewer fan-out will produce overlapping
    findings. Replace the key function here for semantic deduplication.
    """

    def deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicates and return findings sorted by severity desc, confidence desc.
        
        Args:
            findings: Raw findings list (may contain duplicates).
            
        Returns:
            Deduplicated, sorted findings list.
        """
        if not findings:
            return []

        # Group by deduplication key, keep highest confidence per key
        seen: dict[tuple, Finding] = {}
        for finding in findings:
            key = self._key(finding)
            if key not in seen:
                seen[key] = finding
            else:
                existing = seen[key]
                if finding.confidence > existing.confidence:
                    seen[key] = finding
                    logger.debug(
                        "Replaced duplicate finding %r with higher-confidence version",
                        finding.title,
                    )

        removed_count = len(findings) - len(seen)
        if removed_count > 0:
            logger.info("Deduplicator removed %d duplicate findings", removed_count)

        # Sort: CRITICAL first, then by confidence descending
        deduplicated = sorted(
            seen.values(),
            key=lambda f: (_SEVERITY_ORDER.get(f.severity, 0), f.confidence),
            reverse=True,
        )

        return deduplicated

    def _key(self, finding: Finding) -> tuple:
        """Produce the deduplication key for a finding.
        
        Keyed on file + line + normalized title. Case-insensitive title
        comparison prevents near-duplicate titles from the same code location.
        """
        return (
            finding.file,
            finding.line,
            finding.title.lower().strip(),
        )
