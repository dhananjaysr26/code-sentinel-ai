with open("mcp_server/server.py", "r") as f:
    content = f.read()

old_func = """@mcp.tool()
def run_linter(repo_path: str, path: str) -> str:
    \"\"\"Run a deterministic lint/static-analysis tool against a repository file.
    
    Args:
        repo_path: Absolute path to the local git repository.
        path: File path relative to repository root to lint."""

new_func = """import tempfile
import os

@mcp.tool()
def run_linter(repo_path: str, path: str, revision: str = None) -> str:
    \"\"\"Run a deterministic lint/static-analysis tool against a repository file.
    
    Args:
        repo_path: Absolute path to the local git repository.
        path: File path relative to repository root to lint.
        revision: Optional git ref to lint a specific version."""

content = content.replace(old_func, new_func)

old_body = """        # Use ruff from the backend virtualenv if available, or globally
        # Because MCP server might be run from backend/.venv, we'll try to just call `ruff`
        # and fallback to a specific path if needed, but standard `ruff` in PATH works if activated.
        # Alternatively, we can use `sys.executable -m ruff`.
        cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json", str(full_path)]
        
        result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)"""

new_body = """        import tempfile
        import os
        
        target_path = str(full_path)
        temp_fd = None
        temp_path = None
        
        try:
            if revision:
                # Extract the file at the specific revision
                show_cmd = ["git", "show", f"{revision}:{path}"]
                show_res = subprocess.run(show_cmd, cwd=repo, capture_output=True)
                if show_res.returncode == 0:
                    temp_fd, temp_path = tempfile.mkstemp(suffix=".py")
                    with os.fdopen(temp_fd, 'wb') as f:
                        f.write(show_res.stdout)
                    target_path = temp_path
                else:
                    return json.dumps({
                        "path": path,
                        "success": False,
                        "issues": [],
                        "issue_count": 0,
                        "tool": "ruff",
                        "error": {"type": "GitError", "message": show_res.stderr.decode().strip()}
                    })

            cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json", target_path]
            result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)"""

content = content.replace(old_body, new_body)

with open("mcp_server/server.py", "w") as f:
    f.write(content)
