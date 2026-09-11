"""
LangGraph node: parse_diff

Responsibility:
  - Validate the repository path and refs.
  - Call GitService to get the raw unified diff.
  - Call DiffParser to produce structured ChangedFile/DiffHunk objects.
  - Record timing in metadata.

No LLM calls in this node.
"""
import logging
import time

from sentinel.graph.state import ReviewState
from sentinel.services.git_service import GitService, GitServiceError
from sentinel.services.diff_parser import DiffParser

logger = logging.getLogger(__name__)


async def parse_diff_node(state: ReviewState) -> dict:
    """Parse the git diff into structured objects.
    
    Input state fields: repo_path, base_ref, target_ref, metadata
    Output state fields: raw_diff, changed_files, diff_hunks, errors, metadata
    """
    start = time.monotonic()
    repo_path = state["repo_path"]
    base_ref = state["base_ref"]
    target_ref = state["target_ref"]
    errors = list(state.get("errors", []))
    metadata = dict(state.get("metadata", {}))

    logger.info(
        "[%s] parse_diff: %s %s..%s",
        metadata.get("review_id", "?"),
        repo_path,
        base_ref,
        target_ref,
    )

    try:
        git = GitService(repo_path)
    except ValueError as exc:
        msg = f"Invalid repository: {exc}"
        logger.error(msg)
        errors.append(msg)
        return _empty_result(errors, metadata, start)

    # Validate refs
    for ref in (base_ref, target_ref):
        try:
            if not git.validate_ref(ref):
                msg = f"Invalid git ref: {ref!r}"
                logger.error(msg)
                errors.append(msg)
                return _empty_result(errors, metadata, start)
        except GitServiceError as exc:
            msg = f"Ref validation error for {ref!r}: {exc}"
            logger.error(msg)
            errors.append(msg)
            return _empty_result(errors, metadata, start)

    # Get raw diff
    try:
        raw_diff = git.get_diff(base_ref, target_ref)
    except GitServiceError as exc:
        msg = f"git diff failed: {exc}"
        logger.error(msg)
        errors.append(msg)
        return _empty_result(errors, metadata, start)

    # Parse diff
    parser = DiffParser()
    parsed = parser.parse(raw_diff, repo_path)

    # Flatten all hunks across all files
    all_hunks = [
        hunk for file in parsed.changed_files for hunk in file.hunks
    ]

    duration = time.monotonic() - start
    metadata.setdefault("node_durations", {})["parse_diff"] = round(duration, 3)

    logger.info(
        "[%s] parse_diff complete: %d files, %d hunks in %.2fs",
        metadata.get("review_id", "?"),
        len(parsed.changed_files),
        len(all_hunks),
        duration,
    )

    return {
        "raw_diff": raw_diff,
        "changed_files": parsed.changed_files,
        "diff_hunks": all_hunks,
        "errors": errors,
        "metadata": metadata,
    }


def _empty_result(errors: list, metadata: dict, start: float) -> dict:
    """Return an empty result dict when parse_diff fails early."""
    duration = time.monotonic() - start
    metadata.setdefault("node_durations", {})["parse_diff"] = round(duration, 3)
    return {
        "raw_diff": "",
        "changed_files": [],
        "diff_hunks": [],
        "errors": errors,
        "metadata": metadata,
    }
