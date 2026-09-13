with open("backend/tests/test_context_engineering.py", "r") as f:
    content = f.read()

content = content.replace('compacted[5].content == "recent string"', 'compacted[-1].content == "recent string"')

with open("backend/tests/test_context_engineering.py", "w") as f:
    f.write(content)
