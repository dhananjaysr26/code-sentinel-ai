"""
Diff parser: converts raw unified diff text into structured DiffHunk objects.

Uses the `unidiff` library for reliable parsing.
This parser is deterministic and has no LLM dependency.
Unit tested in tests/unit/test_diff_parser.py.
"""
import logging
from typing import Optional

import unidiff

from sentinel.schemas.diff import ChangedFile, DiffHunk, ParsedDiff

logger = logging.getLogger(__name__)


class DiffParser:
    """Parses unified diff text into structured representations.
    
    The LLM is never asked to parse raw diff text. This class handles
    all parsing deterministically so the LLM receives structured, clean input.
    """

    def parse(self, raw_diff: str, repo_path: str = "") -> ParsedDiff:
        """Parse a raw unified diff into a ParsedDiff.
        
        Args:
            raw_diff: Raw output from `git diff`.
            repo_path: Repository root (used for logging only).
            
        Returns:
            ParsedDiff with all changed files and hunks populated.
        """
        if not raw_diff.strip():
            logger.debug("Empty diff provided; returning empty ParsedDiff")
            return ParsedDiff(changed_files=[], total_hunks=0, raw_diff=raw_diff)

        try:
            patch_set = unidiff.PatchSet.from_string(raw_diff)
        except Exception as exc:
            logger.error("Failed to parse diff: %s", exc)
            return ParsedDiff(changed_files=[], total_hunks=0, raw_diff=raw_diff)

        changed_files: list[ChangedFile] = []
        total_hunks = 0

        for patched_file in patch_set:
            file_path = self._normalize_path(patched_file.path)
            old_path: Optional[str] = None

            if patched_file.source_file and patched_file.source_file != patched_file.target_file:
                old_path = self._normalize_path(patched_file.source_file)

            hunks: list[DiffHunk] = []

            for hunk in patched_file:
                added_lines = [
                    line.value for line in hunk if line.is_added
                ]
                removed_lines = [
                    line.value for line in hunk if line.is_removed
                ]
                # Collect new-file line numbers for added lines
                changed_line_numbers = [
                    line.target_line_no
                    for line in hunk
                    if line.is_added and line.target_line_no is not None
                ]

                diff_hunk = DiffHunk(
                    file_path=file_path,
                    old_start=hunk.source_start,
                    old_count=hunk.source_length,
                    new_start=hunk.target_start,
                    new_count=hunk.target_length,
                    hunk_text=str(hunk),
                    added_lines=added_lines,
                    removed_lines=removed_lines,
                    changed_line_numbers=changed_line_numbers,
                )
                hunks.append(diff_hunk)
                total_hunks += 1

            changed_file = ChangedFile(
                path=file_path,
                old_path=old_path,
                is_new=patched_file.is_added_file,
                is_deleted=patched_file.is_removed_file,
                hunks=hunks,
            )
            changed_files.append(changed_file)

        logger.debug(
            "Parsed diff: %d files, %d hunks", len(changed_files), total_hunks
        )

        return ParsedDiff(
            changed_files=changed_files,
            total_hunks=total_hunks,
            raw_diff=raw_diff,
        )

    def _normalize_path(self, path: str) -> str:
        """Strip git diff path prefixes (a/, b/) from file paths.
        
        `git diff` prefixes paths with a/ (old) and b/ (new).
        unidiff typically handles this, but we normalize defensively.
        """
        if path.startswith("b/"):
            return path[2:]
        if path.startswith("a/"):
            return path[2:]
        return path
