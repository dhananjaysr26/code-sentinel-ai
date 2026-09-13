import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

content = content.replace(
    'if stop_reason in ("unknown", "max_iterations", "timeout") and not findings:',
    'if not findings:'
)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
