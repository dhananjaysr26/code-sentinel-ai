with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

content = content.replace(
    'final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\n\n{compact_manifest}"',
    'final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\\n\\n{compact_manifest}"'
)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
