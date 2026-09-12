import asyncio
import os
import time
import json
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel, Field

class Finding(BaseModel):
    file: str = Field(description="File path")
    line: int = Field(description="Line number")
    title: str = Field(description="Title of finding")
    category: str = Field(description="Bug category")
    severity: str = Field(description="Severity (low, medium, high, critical)")
    confidence: float = Field(description="Confidence (0.0 - 1.0)")
    explanation: str = Field(description="Detailed explanation")
    evidence: str = Field(description="Code snippet evidence")
    suggested_fix: str = Field(description="Suggested fix")
    source: str = Field(description="Source of finding")

class ReviewFindings(BaseModel):
    findings: list[Finding] = Field(description="List of bugs found")

async def test_latency():
    print("Initializing ChatBedrockConverse...")
    # Load settings manually since Django is not initialized
    
    # We must properly configure bedrock for the test
    import sys
    sys.path.append("/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    
    llm = ChatBedrockConverse(
        model_id=settings.BEDROCK_MODEL_REASONING,
        region_name=settings.AWS_REGION,
        temperature=0,
    )
    
    # Fake large input context
    print("Creating large input (4500 tokens)...")
    large_text = "def example_function():\n    pass\n" * 1000  # ~4-5k tokens
    
    messages = [
        {"role": "system", "content": "You are a code reviewer. Find bugs."},
        {"role": "user", "content": f"Review this code and return structured output:\n\n{large_text}\n\nReturn an empty findings list if no bugs are found."}
    ]
    
    print("\n--- TEST A: with_structured_output ---")
    structured_llm = llm.with_structured_output(ReviewFindings, include_raw=True)
    start = time.time()
    try:
        res_A = await structured_llm.ainvoke(messages)
        dur_A = time.time() - start
        print(f"Duration: {dur_A:.2f}s")
        raw_A = res_A.get("raw")
        if hasattr(raw_A, "usage_metadata"):
            print(f"Usage: {raw_A.usage_metadata}")
    except Exception as e:
        print(f"Failed: {e}")
        
    print("\n--- TEST B: Plain text JSON ---")
    messages_json = [
        {"role": "system", "content": "You are a code reviewer. Find bugs. Output ONLY JSON with schema: {\"findings\": [{\"file\": \"\", ...}]}"},
        {"role": "user", "content": f"Review this code and return JSON:\n\n{large_text}\n\nReturn an empty findings list if no bugs are found."}
    ]
    start = time.time()
    try:
        res_B = await llm.ainvoke(messages_json)
        dur_B = time.time() - start
        print(f"Duration: {dur_B:.2f}s")
        if hasattr(res_B, "usage_metadata"):
            print(f"Usage: {res_B.usage_metadata}")
        print(f"Response: {res_B.content[:100]}...")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_latency())
