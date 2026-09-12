import asyncio
import os
import time
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel, Field
import subprocess
from langchain_core.messages import SystemMessage, HumanMessage

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

async def reproduce_82s():
    import sys
    sys.path.append("/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    
    # Generate the exact 4500 token input from seed_repo
    repo_path = "/Users/dhananjaysingh/Uncoders/AI_APP/seed_repo"
    from sentinel.context.builder import ContextBuilder
    from sentinel.services.diff_parser import DiffParser
    diff_text = subprocess.check_output(["git", "diff", "1096540", "HEAD"], cwd=repo_path, text=True)
    from sentinel.schemas.context import ContextBudget
    budget = ContextBudget(max_tokens=8000, window_lines=20)
    builder = ContextBuilder(repo_path, budget)
    parser = DiffParser()
    parsed = parser.parse(diff_text, repo_path)
    all_hunks = [hunk for file in parsed.changed_files for hunk in file.hunks]
    context_blocks = await builder.build(all_hunks, repo_path)
    human_content = "Context:\n" + "\n".join(b.model_dump_json() for b in context_blocks)
    
    print(f"Human content length: {len(human_content)}")
    
    from sentinel.graph.nodes.iterative_reviewer import _SECURITY_SYSTEM_PROMPT
    
    messages = [
        SystemMessage(content=_SECURITY_SYSTEM_PROMPT),
        HumanMessage(content=human_content + "\n\nBased on all the context retrieved above, now provide your final findings as JSON. Return ONLY the JSON object.")
    ]
    
    llm = ChatBedrockConverse(
        model_id="deepseek.v3-v1:0",
        region_name="ap-south-1",
        temperature=0,
    )
    
    print("Invoking structured output...")
    start = time.time()
    try:
        res = await llm.with_structured_output(ReviewFindings, include_raw=True).ainvoke(messages)
        dur = time.time() - start
        print(f"Duration: {dur:.2f}s")
        if res.get("raw") and hasattr(res["raw"], "usage_metadata"):
            print(f"Usage: {res['raw'].usage_metadata}")
            
        print(f"Parsed findings: {len(res.get('parsed').findings) if res.get('parsed') else 0}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(reproduce_82s())
