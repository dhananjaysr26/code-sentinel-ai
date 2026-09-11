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
from langchain_core.messages import SystemMessage, HumanMessage

from sentinel.schemas.findings import ReviewFindings, Category
from sentinel.services.llm_service import invoke_structured

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

async def security_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes the diff and context to find security vulnerabilities."""
    start_time = time.monotonic()
    review_id = state.get("metadata", {}).get("review_id", "?")
    blocks = state.get("context_blocks", [])

    logger.info(
        "REVIEWER_START reviewer=security review_id=%s context_blocks=%d",
        review_id, len(blocks),
    )

    if not blocks:
        return {"security_raw_findings": []}

    provider = state.get("llm_provider", settings.LLM_PROVIDER).lower()

    human_content = "Please review the following code changes for insecure patterns:\n\n"
    for block in blocks:
        human_content += f"File: {block.file_path}\n"
        human_content += f"```python\n{block.surrounding_code}\n```\n"
        human_content += f"Diff:\n```diff\n{block.hunk_diff}\n```\n\n"

    system_msg = SystemMessage(content=_SECURITY_SYSTEM_PROMPT)
    human_msg = HumanMessage(content=human_content)

    logger.info("🔒 CALLING LLM PROVIDER: %s (security)", provider.upper())

    try:
        # Note: Retry logic for safety filters is trickier with structured usage,
        # but we do standard invocation here for simplicity
        result = await invoke_structured(provider, [system_msg, human_msg], ReviewFindings)
        parsed_response = result.response
        usage = result.usage
        usage.reviewer = "security"

        # Tag each finding with reviewer='security'
        raw = []
        for f in parsed_response.findings:
            d = f.model_dump()
            d["reviewer"] = "security"
            d["category"] = Category.SECURITY.value
            raw.append(d)

        logger.info(
            "REVIEWER_COMPLETE reviewer=security findings=%d latency_ms=%d tokens=%d",
            len(raw), usage.latency_ms, usage.total_tokens,
        )

        existing_usages = list(state.get("llm_usages", []))
        existing_usages.append(usage.model_dump())

        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["security_ms"] = usage.latency_ms

        return {
            "security_raw_findings": raw,
            "llm_usages": existing_usages,
            "reviewer_latencies": existing_latencies,
        }

    except Exception as exc:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "❌ REVIEWER_FAILED reviewer=security error=%s latency_ms=%d",
            exc, latency_ms,
        )
        error_msg = f"Security reviewer failed ({provider.upper()}): {str(exc)}"
        security_errors = list(state.get("security_errors", []))
        security_errors.append(error_msg)
        
        usage_data = {}
        if len(exc.args) > 1 and hasattr(exc.args[1], "model_dump"):
            usage = exc.args[1]
            usage.reviewer = "security"
            usage_data = usage.model_dump()
        else:
            usage_data = {
                "reviewer": "security",
                "provider": provider,
                "model": "unknown",
                "status": "failed",
                "latency_ms": latency_ms
            }

        existing_usages = list(state.get("llm_usages", []))
        existing_usages.append(usage_data)

        existing_latencies = dict(state.get("reviewer_latencies", {}))
        existing_latencies["security_ms"] = latency_ms

        return {
            "security_raw_findings": [],
            "security_errors": security_errors,
            "llm_usages": existing_usages,
            "reviewer_latencies": existing_latencies,
        }
