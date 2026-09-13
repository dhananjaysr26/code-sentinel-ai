with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

content = content.replace('provide your final structured findings:\n\n{manifest}\n\nNote: The Diff', 'provide your final structured findings:\\n\\n{manifest}\\n\\nNote: The Diff')

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
