import asyncio
import os
import time
import json
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel, Field

class Finding(BaseModel):
    file: str = Field(description="File path")
    line: int = Field(description="Line number")
    title: str = Field(description="Title")
    category: str = Field(description="Bug category")
    severity: str = Field(description="Severity")
    confidence: float = Field(description="Confidence")
    explanation: str = Field(description="Explanation")
    evidence: str = Field(description="Evidence")
    suggested_fix: str = Field(description="Suggested fix")
    source: str = Field(description="Source")

class ReviewFindings(BaseModel):
    findings: list[Finding] = Field(description="List of bugs found")

async def test_empty_findings():
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
    
    messages = [
        {"role": "system", "content": "You are a code reviewer. Find bugs."},
        {"role": "user", "content": "def perfect_function():\n    return True\n"}
    ]
    
    structured_llm = llm.with_structured_output(ReviewFindings, include_raw=True)
    res = await structured_llm.ainvoke(messages)
    
    raw = res.get("raw")
    print(f"Raw Message Object: {raw}")
    if hasattr(raw, "usage_metadata"):
        print(f"Usage: {raw.usage_metadata}")
        
    print(f"Parsed: {res.get('parsed')}")

if __name__ == "__main__":
    asyncio.run(test_empty_findings())
