with open("backend/apps/reviews/overview_views.py", "r") as f:
    content = f.read()

content = content.replace('total_tool_calls=Sum("tool_calls"),', 'total_tool_calls=Sum("mcp_calls"),')

with open("backend/apps/reviews/overview_views.py", "w") as f:
    f.write(content)
