import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

content = content.replace(
    'logger.error("Final structured extraction failed: %s", exc)',
    'logger.error("Final structured extraction failed: %s", exc, exc_info=True)'
)

content = content.replace(
    'logger.error("Final fallback structured call failed: %s", repair_exc)',
    'logger.error("Final fallback structured call failed: %s", repair_exc, exc_info=True)'
)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
