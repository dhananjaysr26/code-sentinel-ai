import asyncio
import os
import time
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel, Field

class Finding(BaseModel):
    file: str = Field(description="File")

class ReviewFindings(BaseModel):
    findings: list[Finding] = Field(description="Bugs")

async def make_request(llm, i):
    print(f"[{i}] Starting request...")
    messages = [
        {"role": "system", "content": "You are a code reviewer."},
        {"role": "user", "content": f"Review this code {i}:\n\n" + "def x(): pass\n"*500}
    ]
    start = time.time()
    try:
        res = await llm.with_structured_output(ReviewFindings, include_raw=True).ainvoke(messages)
        dur = time.time() - start
        print(f"[{i}] Finished in {dur:.2f}s (output tokens: {res['raw'].usage_metadata['output_tokens']})")
        return dur
    except Exception as e:
        dur = time.time() - start
        print(f"[{i}] Failed in {dur:.2f}s: {e}")
        return dur

async def test_parallel():
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
    
    print("Launching 4 parallel requests to simulate LangGraph branching...")
    tasks = [make_request(llm, i) for i in range(4)]
    results = await asyncio.gather(*tasks)
    print(f"Results: {results}")

if __name__ == "__main__":
    asyncio.run(test_parallel())
