import re
import json

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

read_file_params = """
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path from repo root, e.g. 'src/policy.py'",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed). Default 1.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (inclusive). Default 200.",
                    },
                    "justification": {
                        "type": "string",
                        "description": "Why do you need to read this file? What specific information are you looking for?",
                    }
                },
                "required": ["file_path", "justification"],
            },
"""

find_refs_params = """
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The exact function, class, or variable name.",
                    },
                    "justification": {
                        "type": "string",
                        "description": "Why do you need to find this symbol? What specific information are you looking for?",
                    }
                },
                "required": ["symbol", "justification"],
            },
"""

# Replace read_file parameters
content = re.sub(
    r'"parameters":\s*\{\s*"type":\s*"object",\s*"properties":\s*\{\s*"file_path".*?"required":\s*\["file_path"\]\s*,\s*\}',
    read_file_params.strip(),
    content,
    flags=re.DOTALL
)

# Replace find_references parameters
content = re.sub(
    r'"parameters":\s*\{\s*"type":\s*"object",\s*"properties":\s*\{\s*"symbol".*?"required":\s*\["symbol"\]\s*,\s*\}',
    find_refs_params.strip(),
    content,
    flags=re.DOTALL
)

# Update hard limits for tighter budget (per prompt instructions: MAX_TOOL_CALLS = 2/3, ITERATIONS = 3)
content = content.replace('getattr(settings, "ITERATIVE_MAX_ITERATIONS", 5)', 'getattr(settings, "ITERATIVE_MAX_ITERATIONS", 3)')
content = content.replace('getattr(settings, "ITERATIVE_MAX_TOOL_CALLS", 5)', 'getattr(settings, "ITERATIVE_MAX_TOOL_CALLS", 3)')

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
