import re

with open("backend/sentinel/graph/state.py", "r") as f:
    content = f.read()

content = content.replace(
    'tool_cache: Annotated[dict, _merge_dicts]',
    'tool_cache: Annotated[dict, _merge_dicts]\n    evidence_store: Annotated[list, add]'
)

with open("backend/sentinel/graph/state.py", "w") as f:
    f.write(content)
