"""
Review orchestrator: the single entry point for running a code review.

Django views call this service — they do not interact with LangGraph directly.
This boundary keeps LangGraph wiring out of HTTP handler code.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from sentinel.graph.workflow import review_graph
from sentinel.graph.state import ReviewState
from sentinel.schemas.findings import Finding

logger = logging.getLogger(__name__)


class ReviewOrchestrator:
    """Runs the LangGraph review workflow for a single review request.

    Usage (from a Django view):
        orchestrator = ReviewOrchestrator()
        findings, errors, metadata = orchestrator.run_review_sync(
            review_id=str(review.id),
            repo_path=repo_path,
            base_ref=base_ref,
            target_ref=target_ref,
        )
    """

    async def run_review(
        self,
        review_id: str,
        repo_path: str,
        base_ref: str,
        target_ref: str,
        llm_provider: str = "openai",
    ) -> tuple[list[Finding], list[str], dict, list[dict]]:
        """Execute the full review workflow asynchronously.

        Returns:
            (findings, errors, metadata, llm_usages) tuple.
            findings: validated, deduplicated Finding objects.
            errors: list of non-fatal error messages encountered.
            metadata: timing, node durations, finding count.
            llm_usages: list of LLM usage tracking dictionaries.
        """
        logger.info(
            "[%s] Review starting — repo=%s base=%s target=%s",
            review_id, repo_path, base_ref, target_ref,
        )
        start = time.monotonic()

        initial_state: ReviewState = {
            "repo_path": repo_path,
            "base_ref": base_ref,
            "target_ref": target_ref,
            "llm_provider": llm_provider,
            "raw_diff": "",
            "changed_files": [],
            "diff_hunks": [],
            "context_blocks": [],
            "raw_findings": [],
            "findings": [],
            "errors": [],
            "security_errors": [],
            "llm_usages": [],
            "timeline": [],
            "reviewer_latencies": {},
            "metadata": {
                "review_id": review_id,
                "start_time": datetime.now(timezone.utc).isoformat(),
                "node_durations": {},
            },
        }

        final_state = await review_graph.ainvoke(initial_state)

        duration = time.monotonic() - start
        metadata = dict(final_state.get("metadata", {}))
        metadata["total_duration_seconds"] = round(duration, 3)
        metadata["finding_count"] = len(final_state.get("findings", []))
        metadata["reviewer_latencies"] = final_state.get("reviewer_latencies", {})
        metadata["timeline"] = final_state.get("timeline", [])

        logger.info(
            "[%s] Review complete — %d findings in %.2fs",
            review_id,
            metadata["finding_count"],
            duration,
        )

        return (
            final_state.get("findings", []),
            final_state.get("errors", []),
            metadata,
            final_state.get("llm_usages", []),
        )

    def run_review_sync(
        self,
        review_id: str,
        repo_path: str,
        base_ref: str,
        target_ref: str,
        llm_provider: str = "openai",
    ) -> tuple[list[Finding], list[str], dict, list[dict]]:
        """Synchronous wrapper for use from Django sync views.

        Uses asyncio.run() to execute the async workflow.
        Safe to call from a non-async Django view.
        """
        return asyncio.run(
            self.run_review(
                review_id=review_id,
                repo_path=repo_path,
                base_ref=base_ref,
                target_ref=target_ref,
                llm_provider=llm_provider,
            )
        )
