import json
import logging
from typing import Any, Dict

from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from sentinel.schemas.findings import ReviewFindings, Finding, Severity, Category, Source

logger = logging.getLogger(__name__)

async def correctness_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyzes the diff and context to find correctness bugs."""
    logger.info("[%s] correctness_review: analyzing %d blocks", state.get("review_id"), len(state.get("context_blocks", [])))
    
    if not state.get("context_blocks"):
        return {"findings": []}
        
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
                # If a bearer token is provided, use it (it might be an API key or session token for a proxy)
                kwargs["aws_session_token"] = settings.AWS_BEARER_TOKEN_BEDROCK
                # Some custom endpoints use bedrock_api_key in Langchain
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
                "2. Be thorough — examine every changed line for potential runtime errors.\n"
                "3. For EACH finding you MUST provide ALL of these fields:\n"
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
                "If there are truly no bugs, return {\"findings\": []}."
            )
        )
        
        # Build prompt from context blocks
        blocks = state.get("context_blocks", [])
        human_content = "Please review the following code changes:\n\n"
        for block in blocks:
            human_content += f"File: {block.file_path}\n"
            human_content += f"```python\n{block.surrounding_code}\n```\n"
            human_content += f"Diff:\n```diff\n{block.hunk_diff}\n```\n\n"
            
        human_msg = HumanMessage(content=human_content)
        
        logger.info("==================================================")
        logger.info("🚀 CALLING LLM PROVIDER: %s", provider.upper())
        if provider == "bedrock":
            logger.info("   Model ID: %s", settings.BEDROCK_MODEL_REASONING)
            logger.info("   Profile: %s | Region: %s", settings.AWS_PROFILE, settings.AWS_REGION)
        else:
            logger.info("   Model: %s", settings.OPENAI_MODEL)
        logger.info("   Context size: %d context blocks", len(blocks))
        logger.info("==================================================")
        
        result = await structured_llm.ainvoke([system_msg, human_msg])
        
        logger.info("✅ LLM call SUCCESS! Received %d real findings from AI.", len(result.findings))
        return {"raw_findings": [f.model_dump() for f in result.findings]}
        
    except Exception as exc:
        logger.error("❌ LLM CALL FAILED! Error from %s: %s", provider.upper(), exc)
        error_msg = f"LLM call failed ({provider.upper()}): {str(exc)}"
        errors = list(state.get("errors", []))
        errors.append(error_msg)
        return {"raw_findings": [], "errors": errors}
