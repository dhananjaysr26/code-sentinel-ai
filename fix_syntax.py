with open("backend/sentinel/graph/context_engineering.py", "r") as f:
    content = f.read()

content = content.replace('lines.append("```\n")', 'lines.append("```")')
content = content.replace('lines.append("\n(Raw content stored in evidence_store. Re-fetch via MCP only if new details are needed).")', 'lines.append("\\n(Raw content stored in evidence_store. Re-fetch via MCP only if new details are needed).")')
content = content.replace('return "\n".join(lines)', 'return "\\n".join(lines)')

with open("backend/sentinel/graph/context_engineering.py", "w") as f:
    f.write(content)
