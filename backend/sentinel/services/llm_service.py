import time
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
async def _execute_with_retry(llm_with_struct, messages):
    return await llm_with_struct.ainvoke(messages)

from typing import Any, Dict, List, Type
from pydantic import BaseModel
import tiktoken

def estimate_tokens(text: str) -> int:
    if not text: return 0
    try:
        enc = tiktoken.get_encoding('cl100k_base')
        return len(enc.encode(text))
    except:
        return len(text) // 4


from django.conf import settings
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrockConverse

from sentinel.services.pricing import calculate_cost

logger = logging.getLogger(__name__)

class LLMUsage(BaseModel):
    provider: str
    model: str
    reviewer: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    estimated_cost: float | None = None
    request_count: int = 1
    status: str = "success"
    phase: str = ""
    message_count: int = 0
    source_code_tokens: int = 0
    diff_tokens: int = 0
    system_prompt_tokens: int = 0
    reviewer_prompt_tokens: int = 0
    tool_schema_tokens: int = 0
    history_tokens: int = 0
    tool_result_tokens: int = 0
    structured_schema_tokens: int = 0

class LLMInvocationResult(BaseModel):
    response: Any
    usage: LLMUsage

def get_llm(provider: str):
    if provider == "bedrock":
        kwargs = {
            "model_id": settings.BEDROCK_MODEL_REASONING,
            "region_name": settings.AWS_REGION,
            "temperature": 0,
        }
        if hasattr(settings, "AWS_BEARER_TOKEN_BEDROCK") and settings.AWS_BEARER_TOKEN_BEDROCK:
            kwargs["aws_session_token"] = settings.AWS_BEARER_TOKEN_BEDROCK
            kwargs["bedrock_api_key"] = settings.AWS_BEARER_TOKEN_BEDROCK
        else:
            kwargs["credentials_profile_name"] = getattr(settings, "AWS_PROFILE", "default")
        return ChatBedrockConverse(**kwargs)
    else:
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0,
            api_key=settings.OPENAI_API_KEY,
        )

def _normalize_usage(provider: str, model: str, raw_msg: Any, latency_ms: int) -> LLMUsage:
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0

    if hasattr(raw_msg, "usage_metadata") and raw_msg.usage_metadata:
        meta = raw_msg.usage_metadata
        input_tokens = meta.get("input_tokens", 0)
        output_tokens = meta.get("output_tokens", 0)
        total_tokens = meta.get("total_tokens", 0)
    elif hasattr(raw_msg, "response_metadata") and raw_msg.response_metadata:
        # Fallback extraction just in case
        meta = raw_msg.response_metadata
        if "token_usage" in meta: # OpenAI fallback
            input_tokens = meta["token_usage"].get("prompt_tokens", 0)
            output_tokens = meta["token_usage"].get("completion_tokens", 0)
            total_tokens = meta["token_usage"].get("total_tokens", 0)
        elif "amazon-bedrock-invocationMetrics" in meta: # Bedrock fallback
            metrics = meta["amazon-bedrock-invocationMetrics"]
            input_tokens = metrics.get("inputTokenCount", 0)
            output_tokens = metrics.get("outputTokenCount", 0)
            total_tokens = input_tokens + output_tokens

    estimated_cost = calculate_cost(model, input_tokens, output_tokens)

    return LLMUsage(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        estimated_cost=estimated_cost,
    )

from langsmith import traceable

@traceable(run_type="llm", name="invoke_structured_output")
async def invoke_structured(
    provider: str, 
    messages: List[BaseMessage], 
    schema: Type[BaseModel]
) -> LLMInvocationResult:
    """Invokes LLM with structured output and extracts usage."""
    llm = get_llm(provider)
    
    if provider == "bedrock":
        model_name = settings.BEDROCK_MODEL_REASONING
    else:
        model_name = settings.OPENAI_MODEL

    start_time = time.monotonic()
    
    try:
        structured_llm = llm.with_structured_output(schema, include_raw=True)
        # Using Tenacity for robust exponential backoff as per expert pattern
        result = await _execute_with_retry(structured_llm, messages)
        latency_ms = int((time.monotonic() - start_time) * 1000)
        
        parsed = result.get("parsed")
        raw = result.get("raw")
        
        usage = _normalize_usage(provider, model_name, raw, latency_ms)
        return LLMInvocationResult(response=parsed, usage=usage)
        
    except Exception as e:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(f"LLM structured invocation failed permanently: {e}")
        usage = LLMUsage(
            provider=provider,
            model=model_name,
            latency_ms=latency_ms,
            status="failed",
        )
        raise RuntimeError(f"LLM error: {str(e)}", usage)
