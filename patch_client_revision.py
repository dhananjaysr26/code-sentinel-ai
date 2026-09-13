with open("backend/sentinel/mcp/client.py", "r") as f:
    content = f.read()

old_call = """        result = await self._call_tool(
            "run_linter",
            {
                "repo_path": repo_path,
                "path": path,
            },
        )"""

new_call = """        args = {
            "repo_path": repo_path,
            "path": path,
        }
        if revision is not None:
            args["revision"] = revision
            
        result = await self._call_tool(
            "run_linter",
            args,
        )"""

content = content.replace(old_call, new_call)
with open("backend/sentinel/mcp/client.py", "w") as f:
    f.write(content)
