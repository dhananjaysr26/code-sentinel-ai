import re
with open("backend/sentinel/graph/context_planner.py", "r") as f:
    content = f.read()

# Fix the broken line
old_broken = '''            file_diff_pattern = r"(?:^|
)diff --git a/" + re.escape(file) + r" b/.*?(?=
diff --git|$)"'''

new_fixed = r'            file_diff_pattern = r"(?:^|\n)diff --git a/" + re.escape(file) + r" b/.*?(?=\ndiff --git|$)"'

content = content.replace(old_broken, new_fixed)

with open("backend/sentinel/graph/context_planner.py", "w") as f:
    f.write(content)
