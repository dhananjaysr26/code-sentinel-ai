import re

text = "@@ -24,8 +24,9 @@ def parse(self, raw_diff: str, repo_path: str = \"\") -> ParsedDiff:"
match = re.search(r"@@.*?@@.*?(?:(?:async\s+)?def|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)", text)
print(match.group(1) if match else "No match")
