import re
with open("backend/sentinel/context/builder.py", "r") as f:
    content = f.read()

# Replace find_references logic with empty block
pattern = r"# Fetch references using the new MCP tool\s+try:.*?(?=except Exception as exc:)"
replacement = """# Removed find_references aggressive pre-fetching to save tokens.
                # LLM can use find_references tool in ReAct loop if it decides it needs callers.
        """
content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open("backend/sentinel/context/builder.py", "w") as f:
    f.write(content)
