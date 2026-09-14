import asyncio
import os
import time
import json
from langchain_aws import ChatBedrockConverse

async def test_deepseek():
    import sys
    sys.path.append("/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    
    # Force deepseek
    llm = ChatBedrockConverse(
        model_id="deepseek.v3-v1:0",
        region_name="ap-south-1",
        temperature=0,
    )
    
    messages = [
        {"role": "system", "content": "You are a code reviewer."},
        {"role": "user", "content": "Write a 100 line python script to calculate fibonacci."}
    ]
    
    print("Testing raw invoke to see if it generates reasoning tokens...")
    start = time.time()
    res = await llm.ainvoke(messages)
    dur = time.time() - start
    
    print(f"Duration: {dur:.2f}s")
    print(f"Content length: {len(res.content)}")
    if hasattr(res, "usage_metadata"):
        print(f"Usage: {res.usage_metadata}")
        
    print(f"Raw dict: {res.dict()}")

if __name__ == "__main__":
    asyncio.run(test_deepseek())
