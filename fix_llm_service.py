import re

with open("backend/sentinel/services/llm_service.py", "r") as f:
    content = f.read()

import_tiktoken = "import tiktoken\n\ndef estimate_tokens(text: str) -> int:\n    if not text: return 0\n    try:\n        enc = tiktoken.get_encoding('cl100k_base')\n        return len(enc.encode(text))\n    except:\n        return len(text) // 4\n"

content = content.replace("from pydantic import BaseModel", "from pydantic import BaseModel\n" + import_tiktoken)

usage_fields = """    phase: str = ""
    message_count: int = 0
    source_code_tokens: int = 0
    diff_tokens: int = 0
    system_prompt_tokens: int = 0
    reviewer_prompt_tokens: int = 0
    tool_schema_tokens: int = 0
    history_tokens: int = 0
    tool_result_tokens: int = 0
    structured_schema_tokens: int = 0"""

content = content.replace('    status: str = "success"', '    status: str = "success"\n' + usage_fields)

with open("backend/sentinel/services/llm_service.py", "w") as f:
    f.write(content)
