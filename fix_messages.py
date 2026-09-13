import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

# Fix Branch B
content = content.replace(
    'final_messages = messages + [response, closing_msg] if getattr(response, "content", "") else messages + [closing_msg]',
    'final_messages = messages'
)

# Fix fallback
content = content.replace(
    'repair_result = await invoke_structured(provider, messages + [closing_msg], ReviewFindings)',
    'repair_result = await invoke_structured(provider, messages, ReviewFindings)'
)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
