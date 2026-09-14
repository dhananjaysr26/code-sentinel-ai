import asyncio
import os
import time
import sys
from langchain_aws import ChatBedrockConverse
from botocore.config import Config
from pydantic import BaseModel, Field

class Finding(BaseModel):
    file: str = Field(description="File")

class ReviewFindings(BaseModel):
    findings: list[Finding] = Field(description="Bugs")

async def test_no_retries():
    sys.path.append("/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    
    config = Config(retries={'max_attempts': 0})
    llm = ChatBedrockConverse(
        model_id="deepseek.v3-v1:0",
        region_name="ap-south-1",
        temperature=0,
        client_kwargs={"config": config}
    )
    
    messages = [
        {"role": "user", "content": "Hello! " * 2000}
    ]
    
    start = time.time()
    try:
        res = await llm.ainvoke(messages)
        dur = time.time() - start
        print(f"Success in {dur:.2f}s")
    except Exception as e:
        dur = time.time() - start
        print(f"Failed in {dur:.2f}s: {e}")

if __name__ == "__main__":
    asyncio.run(test_no_retries())
