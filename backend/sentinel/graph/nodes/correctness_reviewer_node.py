import logging
import time
from typing import Any, Dict

from django.conf import settings
from langchain_core.messages import SystemMessage, HumanMessage

from sentinel.schemas.findings import ReviewFindings
from sentinel.services.llm_service import invoke_structured

logger = logging.getLogger(__name__)

async def correctness_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes the diff and context to find correctness bugs."""
    start_time = time.monotonic()
    review_id = state.get("metadata", {}).get("review_id", "?")
    blocks = state.get("context_blocks", [])

    logger.info(
        "REVIEWER_START reviewer=correctness review_id=%s context_blocks=%d",
        review_id, len(blocks),
    )

    if not blocks:
        return {"correctness_raw_findings": []}

    provider = state.get("llm_provider", settings.LLM_PROVIDER).lower()

    system_msg = SystemMessage(
        content=(
            "You are CodeSentinel AI, an expert automated code reviewer.\n\n"
            "TASK: Carefully analyze each code diff hunk and its surrounding context below. "
            "Identify ALL correctness bugs including:\n"
            "- NoneType / null dereferences\n"
            "- Off-by-one errors (e.g. wrong range boundary)\n"
            "- Inverted boolean conditions\n"
            "- Resource leaks (e.g. file handles not closed)\n"
            "- Missing key checks (e.g. dict['key'] without .get())\n"
            "- Logic errors and incorrect return values\n\n"
            "RULES:\n"
            "1. Only report genuine correctness bugs, NOT style issues.\n"
            "2. Do NOT report security vulnerabilities — those are handled by a separate reviewer.\n"
            "3. Be thorough — examine every changed line for potential runtime errors.\n"
            "4. For EACH finding you MUST provide ALL of these fields:\n"
            "   - file: the relative file path (e.g. 'src/user.py')\n"
            "   - line: the exact line number of the bug\n"
            "   - title: a short descriptive title\n"
            "   - category: must be 'correctness'\n"
            "   - severity: one of 'critical', 'high', 'medium', 'low'\n"
            "   - confidence: a float between 0.0 and 1.0\n"
            "   - explanation: a detailed explanation of WHY this is a bug\n"
            "   - evidence: the exact code snippet containing the bug\n"
            "   - suggested_fix: the corrected code\n"
            "   - source: must be 'llm'\n\n"
            "If there are truly no correctness bugs, return {\"findings\": []}."
        )
    )

    human_content = "Please review the following code changes:\n\n"
    for block in blocks:
        human_content += f"File: {block.file_path}\n"
        human_content += f"```python\n{block.surrounding_code}\n```\n"
        human_content += f"Diff:\n```diff\n{block.hunk_diff}\n```\n\n"

    human_msg = HumanMessage(content=human_content)

    logger.info("🚀 CALLING LLM PROVIDER: %s (correctness)", provider.upper())

    try:
        result = await invoke_structured(provider, [system_msg, human_msg], ReviewFindings)
        parsed_response = result.response
        usage = result.usage
        usage.reviewer = "correctness"

        # Tag each finding with reviewer='correctness'
        raw = []
        for f in parsed_response.findings:
            d = f.model_dump()
            d["reviewer"] = "correctness"
            raw.append(d)

        logger.info(
            "REVIEWER_COMPLETE reviewer=correctness findings=%d latency_ms=%d tokens=%d",
            len(raw), usage.latency_ms, usage.total_tokens,
        )

        existing_usages = list(state.get("llm_usages", []))
        existing_usages.append(usage.model_dump())
        
        # Keep old latencies dictionary to not break other assumptions just in case
        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["correctness_ms"] = usage.latency_ms

        return {
            "correctness_raw_findings": raw,
            "llm_usages": existing_usages,
            "reviewer_latencies": existing_latencies,
        }

    except Exception as exc:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "❌ REVIEWER_FAILED reviewer=correctness error=%s latency_ms=%d",
            exc, latency_ms,
        )
        error_msg = f"Correctness reviewer failed ({provider.upper()}): {str(exc)}"
        errors = list(state.get("errors", []))
        errors.append(error_msg)
        
        usage_data = {}
        if len(exc.args) > 1 and hasattr(exc.args[1], "model_dump"):
            usage = exc.args[1]
            usage.reviewer = "correctness"
            usage_data = usage.model_dump()
        else:
            usage_data = {
                "reviewer": "correctness",
                "provider": provider,
                "model": "unknown",
                "status": "failed",
                "latency_ms": latency_ms
            }

        existing_usages = list(state.get("llm_usages", []))
        existing_usages.append(usage_data)

        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["correctness_ms"] = latency_ms

        return {
            "correctness_raw_findings": [],
            "errors": errors,
            "llm_usages": existing_usages,
            "reviewer_latencies": existing_latencies,
        }
