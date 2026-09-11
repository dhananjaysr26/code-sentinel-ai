"""
Security Reviewer LangGraph node.

Responsibility: ONLY security analysis.
Runs in PARALLEL with correctness_review_node after build_context.

Focus areas:
- Injection vulnerabilities (SQL, command, template)
- Authentication / authorization bypass
- Hardcoded secrets and credential exposure
- Missing input validation on user-controlled data
- Unsafe file handling

This node is INDEPENDENT of the correctness reviewer.
One failing does not affect the other.
"""
import logging
import time
from typing import Any, Dict

from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from sentinel.schemas.findings import ReviewFindings, Category

logger = logging.getLogger(__name__)

_SECURITY_SYSTEM_PROMPT = """You are a senior code quality engineer reviewing a code change.

Your task is to identify insecure coding patterns and safety issues introduced by the change.

Analyze ONLY the provided diff and relevant repository context.
Prioritize reproducible issues over stylistic advice.
Do NOT report hypothetical issues without evidence in the provided code.

Focus on these vulnerability classes:
- Unsafe database queries: user-controlled input interpolated into raw SQL strings
- Unsafe shell execution: user input passed to os.system, subprocess, or shell=True
- Hardcoded secrets: API keys, passwords, tokens committed in source code
- Missing authorization: admin or sensitive endpoints accessed without role/permission checks
- Unsafe input handling: direct use of untrusted user data without validation or sanitization
- Unsafe file handling: path traversal, unchecked file uploads, unsafe open() calls
- Credential logging: sensitive data written to logs

For every finding you MUST provide ALL of these fields:
- file: the relative file path (e.g. 'src/db.py')
- line: the exact line number of the vulnerability
- title: a short, specific title
- category: must be 'security'
- severity: one of 'critical', 'high', 'medium', 'low'
- confidence: a float between 0.0 and 1.0
- explanation: why this code is vulnerable, including the mechanism
- evidence: the exact vulnerable code snippet
- suggested_fix: the corrected, safe code
- source: must be 'llm'

If no credible security vulnerability exists in the diff, return {"findings": []}.
Do NOT report findings you cannot directly support with code from the diff."""


def _build_llm(provider: str, settings_obj: Any):
    """Reuse the same LLM provider abstraction as correctness reviewer."""
    if provider == "bedrock":
        from langchain_aws import ChatBedrockConverse
        kwargs = {
            "model_id": settings_obj.BEDROCK_MODEL_REASONING,
            "region_name": settings_obj.AWS_REGION,
            "temperature": 0.1,  # slightly above 0 to allow retry variance
        }
        if hasattr(settings_obj, "AWS_BEARER_TOKEN_BEDROCK") and settings_obj.AWS_BEARER_TOKEN_BEDROCK:
            kwargs["aws_session_token"] = settings_obj.AWS_BEARER_TOKEN_BEDROCK
            kwargs["bedrock_api_key"] = settings_obj.AWS_BEARER_TOKEN_BEDROCK
            logger.info("   Auth: Using API Key / Bearer Token")
        else:
            kwargs["credentials_profile_name"] = settings_obj.AWS_PROFILE
            logger.info("   Auth: Using AWS Profile %s", settings_obj.AWS_PROFILE)
        return ChatBedrockConverse(**kwargs)
    else:
        return ChatOpenAI(
            model=settings_obj.OPENAI_MODEL,
            temperature=0.1,
            api_key=settings_obj.OPENAI_API_KEY or "dummy",
        )


async def security_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes the diff and context to find security vulnerabilities.

    Runs in parallel with correctness_review_node after build_context.
    Failure is isolated — correctness findings are preserved if this fails.
    Returns security_raw_findings for the merge node to combine.
    """
    start_time = time.monotonic()
    review_id = state.get("metadata", {}).get("review_id", "?")
    blocks = state.get("context_blocks", [])

    logger.info(
        "REVIEWER_START reviewer=security review_id=%s context_blocks=%d",
        review_id, len(blocks),
    )

    if not blocks:
        return {"security_raw_findings": []}

    provider = "unknown"
    try:
        provider = state.get("llm_provider", settings.LLM_PROVIDER).lower()
        llm = _build_llm(provider, settings)
        structured_llm = llm.with_structured_output(ReviewFindings)

        human_content = "Please review the following code changes for insecure patterns:\n\n"
        for block in blocks:
            human_content += f"File: {block.file_path}\n"
            human_content += f"```python\n{block.surrounding_code}\n```\n"
            human_content += f"Diff:\n```diff\n{block.hunk_diff}\n```\n\n"

        system_msg = SystemMessage(content=_SECURITY_SYSTEM_PROMPT)
        human_msg = HumanMessage(content=human_content)

        logger.info("==================================================")
        logger.info("🔒 CALLING LLM PROVIDER: %s (security)", provider.upper())
        if provider == "bedrock":
            logger.info("   Model ID: %s", settings.BEDROCK_MODEL_REASONING)
        else:
            logger.info("   Model: %s", settings.OPENAI_MODEL)
        logger.info("   Context size: %d context blocks", len(blocks))
        logger.info("==================================================")

        MAX_RETRIES = 2
        result = None
        for attempt in range(MAX_RETRIES + 1):
            call_start = time.monotonic()
            result = await structured_llm.ainvoke([system_msg, human_msg])
            call_latency = time.monotonic() - call_start
            
            # Heuristic: If it returns 0 findings very fast, it is likely a safety filter refusal
            if len(result.findings) == 0 and call_latency < 2.0 and attempt < MAX_RETRIES:
                logger.warning(
                    "⚠️ Security LLM returned 0 findings in %.2fs (Safety filter?). Retrying attempt %d...",
                    call_latency, attempt + 1
                )
                continue
                
            # Valid response (either >0 findings, or a legitimately slow 0 findings)
            break

        # Tag each finding with reviewer='security'
        raw = []
        for f in result.findings:
            d = f.model_dump()
            d["reviewer"] = "security"
            # Ensure category is always 'security' regardless of what model returned
            d["category"] = Category.SECURITY.value
            raw.append(d)

        latency_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "REVIEWER_COMPLETE reviewer=security findings=%d latency_ms=%d",
            len(raw), latency_ms,
        )

        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["security_ms"] = latency_ms

        return {
            "security_raw_findings": raw,
            "reviewer_latencies": existing_latencies,
        }

    except Exception as exc:
        latency_ms = round((time.monotonic() - start_time) * 1000)
        logger.error(
            "❌ REVIEWER_FAILED reviewer=security error=%s latency_ms=%d",
            exc, latency_ms,
        )
        # ISOLATION: security failure does NOT affect correctness findings
        # Return empty security findings + record error separately
        error_msg = f"Security reviewer failed ({provider.upper()}): {str(exc)}"
        security_errors = list(state.get("security_errors", []))
        security_errors.append(error_msg)
        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["security_ms"] = latency_ms
        return {
            "security_raw_findings": [],
            "security_errors": security_errors,
            "reviewer_latencies": existing_latencies,
        }
