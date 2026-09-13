import re
with open("backend/sentinel/mcp/client.py", "r") as f:
    content = f.read()

content = content.replace(
    "async def run_linter(\n        self, repo_path: str, path: str\n    ) -> str:",
    "async def run_linter(\n        self, repo_path: str, path: str, revision: str = None\n    ) -> str:"
)

old_body = """        result = await self.session.call_tool(
            "run_linter",
            arguments={"repo_path": repo_path, "path": path},
        )"""
new_body = """        args = {"repo_path": repo_path, "path": path}
        if revision:
            args["revision"] = revision
        result = await self.session.call_tool(
            "run_linter",
            arguments=args,
        )"""

content = content.replace(old_body, new_body)

with open("backend/sentinel/mcp/client.py", "w") as f:
    f.write(content)
