import asyncio
import os
import time
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage
import subprocess

async def test_tool_calling():
    import sys
    sys.path.append("/Users/dhananjaysingh/Uncoders/AI_APP/code-sentinel-ai/backend")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from sentinel.context.builder import ContextBuilder
    from sentinel.services.diff_parser import DiffParser
    from sentinel.schemas.context import ContextBudget
    
    repo_path = "/Users/dhananjaysingh/Uncoders/AI_APP/seed_repo"
    diff_text = subprocess.check_output(["git", "diff", "1096540", "HEAD"], cwd=repo_path, text=True)
    budget = ContextBudget(max_tokens=8000, window_lines=20)
    builder = ContextBuilder(repo_path, budget)
    parser = DiffParser()
    parsed = parser.parse(diff_text, repo_path)
    all_hunks = [hunk for file in parsed.changed_files for hunk in file.hunks]
    context_blocks = await builder.build(all_hunks, repo_path)
    human_content = "Context:\n" + "\n".join(b.model_dump_json() for b in context_blocks)
    
    from sentinel.graph.nodes.iterative_reviewer import _SECURITY_SYSTEM_PROMPT, MCP_TOOL_DEFINITIONS
    
    messages = [
        SystemMessage(content=_SECURITY_SYSTEM_PROMPT),
        HumanMessage(content=human_content)
    ]
    
    llm = ChatBedrockConverse(
        model_id="deepseek.v3-v1:0",
        region_name=settings.AWS_REGION,
        temperature=0,
    )
    
    # Bind the exact same tools
    llm_with_tools = llm.bind_tools(MCP_TOOL_DEFINITIONS)
    
    print("Invoking llm with tools...")
    start = time.time()
    try:
        res = await llm_with_tools.ainvoke(messages)
        dur = time.time() - start
        print(f"Duration: {dur:.2f}s")
        if hasattr(res, "usage_metadata"):
            print(f"Usage: {res.usage_metadata}")
        print(f"Tool calls: {res.tool_calls}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool_calling())
