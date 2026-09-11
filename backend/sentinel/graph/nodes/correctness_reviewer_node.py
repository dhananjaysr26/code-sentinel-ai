import logging
import time
from typing import Any, Dict

from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from sentinel.schemas.findings import ReviewFindings, Finding, Severity, Category, Source

logger = logging.getLogger(__name__)

async def correctness_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes the diff and context to find correctness bugs.

    Runs in parallel with security_review_node after build_context.
    Returns correctness_raw_findings so the merge node can combine both.
    """
    start_time = time.monotonic()
    review_id = state.get("metadata", {}).get("review_id", "?")
    blocks = state.get("context_blocks", [])

    logger.info(
        "REVIEWER_START reviewer=correctness review_id=%s context_blocks=%d",
        review_id, len(blocks),
    )

    if not blocks:
        return {"correctness_raw_findings": []}

    provider = "unknown"
    try:
        provider = state.get("llm_provider", settings.LLM_PROVIDER).lower()

        if provider == "bedrock":
            from langchain_aws import ChatBedrockConverse
            kwargs = {
                "model_id": settings.BEDROCK_MODEL_REASONING,
                "region_name": settings.AWS_REGION,
                "temperature": 0,
            }
            if hasattr(settings, "AWS_BEARER_TOKEN_BEDROCK") and settings.AWS_BEARER_TOKEN_BEDROCK:
                kwargs["aws_session_token"] = settings.AWS_BEARER_TOKEN_BEDROCK
                kwargs["bedrock_api_key"] = settings.AWS_BEARER_TOKEN_BEDROCK
                logger.info("   Auth: Using API Key / Bearer Token")
            else:
                kwargs["credentials_profile_name"] = settings.AWS_PROFILE
                logger.info("   Auth: Using AWS Profile %s", settings.AWS_PROFILE)
            llm = ChatBedrockConverse(**kwargs)
        else:
            llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=0,
                api_key=settings.OPENAI_API_KEY or "dummy",
            )

        structured_llm = llm.with_structured_output(ReviewFindings)

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

        logger.info("==================================================")
        logger.info("🚀 CALLING LLM PROVIDER: %s (correctness)", provider.upper())
        if provider == "bedrock":
            logger.info("   Model ID: %s", settings.BEDROCK_MODEL_REASONING)
        else:
            logger.info("   Model: %s", settings.OPENAI_MODEL)
        logger.info("   Context size: %d context blocks", len(blocks))
        logger.info("==================================================")

        result = await structured_llm.ainvoke([system_msg, human_msg])

        # Tag each finding with reviewer='correctness'
        raw = []
        for f in result.findings:
            d = f.model_dump()
            d["reviewer"] = "correctness"
            raw.append(d)

        latency_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "REVIEWER_COMPLETE reviewer=correctness findings=%d latency_ms=%d",
            len(raw), latency_ms,
        )

        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["correctness_ms"] = latency_ms

        return {
            "correctness_raw_findings": raw,
            "reviewer_latencies": existing_latencies,
        }

    except Exception as exc:
        latency_ms = round((time.monotonic() - start_time) * 1000)
        logger.error(
            "❌ REVIEWER_FAILED reviewer=correctness error=%s latency_ms=%d",
            exc, latency_ms,
        )
        error_msg = f"Correctness reviewer failed ({provider.upper()}): {str(exc)}"
        errors = list(state.get("errors", []))
        errors.append(error_msg)
        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["correctness_ms"] = latency_ms
        return {
            "correctness_raw_findings": [],
            "errors": errors,
            "reviewer_latencies": existing_latencies,
        }
