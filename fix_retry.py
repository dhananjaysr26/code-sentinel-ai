import re

with open("backend/sentinel/services/llm_service.py", "r") as f:
    content = f.read()

retry_code = """
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
async def _execute_with_retry(llm_with_struct, messages):
    return await llm_with_struct.ainvoke(messages)
"""

if "_execute_with_retry(llm_with_struct" not in content:
    content = content.replace("import logging", "import logging\n" + retry_code)

with open("backend/sentinel/services/llm_service.py", "w") as f:
    f.write(content)
