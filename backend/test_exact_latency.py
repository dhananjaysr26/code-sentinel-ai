import asyncio
import os
import time
import json
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

class Finding(BaseModel):
    file: str = Field(description="File")
    line: int = Field(description="Line")
    title: str = Field(description="Title")
    category: str = Field(description="Category")
    severity: str = Field(description="Severity")
    confidence: float = Field(description="Confidence")
    explanation: str = Field(description="Explanation")
    evidence: str = Field(description="Evidence")
    suggested_fix: str = Field(description="Fix")
    source: str = Field(description="Source")

class ReviewFindings(BaseModel):
    findings: list[Finding] = Field(description="List of bugs found")

async def test_variants():
    import sys
    sys.path.append("/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from sentinel.context.builder import ContextBuilder
    from sentinel.utils.git import parse_diff
    import subprocess
    
    # Get the real diff
    repo_path = "/Users/dhananjaysingh/Uncoders/AI_APP/seed_repo"
    diff_text = subprocess.check_output(
        ["git", "diff", "1096540", "HEAD"], cwd=repo_path, text=True
    )
    parsed_diff = parse_diff(diff_text)
    builder = ContextBuilder(repo_path, max_tokens=8000, window_lines=20)
    context_blocks = await builder.build_context(parsed_diff)
    
    human_content = "Context:\n" + "\n".join(b.content for b in context_blocks)
    
    system_prompt = """You are a senior security code reviewer. Only report security bugs."""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content)
    ]
    
    llm = ChatBedrockConverse(
        model_id="deepseek.v3-v1:0",
        region_name=settings.AWS_REGION,
        temperature=0,
    )
    
    print("\n=== Variant A: with_structured_output ===")
    start = time.time()
    try:
        res_A = await llm.with_structured_output(ReviewFindings, include_raw=True).ainvoke(messages)
        print(f"Dur: {time.time() - start:.2f}s, Usage: {res_A['raw'].usage_metadata}, Parsed count: {len(res_A['parsed'].findings) if res_A.get('parsed') else 0}")
    except Exception as e:
        print(f"Error: {e}")
        
    print("\n=== Variant B: Plain JSON Mode ===")
    messages_json = [
        SystemMessage(content=system_prompt + "\nReturn ONLY JSON matching {'findings': [...]}"),
        HumanMessage(content=human_content)
    ]
    start = time.time()
    try:
        res_B = await llm.ainvoke(messages_json)
        print(f"Dur: {time.time() - start:.2f}s, Usage: {res_B.usage_metadata}")
        print(f"Response: {res_B.content[:200]}...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_variants())
