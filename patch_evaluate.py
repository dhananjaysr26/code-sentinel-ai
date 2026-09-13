import re
with open("evaluate.py", "r") as f:
    content = f.read()

content = content.replace("for f in db_findings:", "for f in [x for x in db_findings if x.source != 'linter']:")

with open("evaluate.py", "w") as f:
    f.write(content)
