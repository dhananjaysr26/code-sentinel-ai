import re
with open("mcp_server/server.py", "r") as f:
    content = f.read()

old_func = """def run_linter(repo_path: str, path: str) -> str:
    \"\"\"Run a deterministic lint/static-analysis tool against a repository file.
    
    Args:
        repo_path: Absolute path to the local git repository.
        path: File path relative to repository root to lint.
        
    Returns:
        JSON string containing structured lint issues.
    \"\"\"
    try:
        repo = _validate_repo(repo_path)
        full_path = _validate_file_path(repo, path)
        
        # We only support Python files with ruff for now
        if not path.endswith(".py"):
            return json.dumps({
                "path": path,
                "success": False,
                "issues": [],
                "issue_count": 0,
                "tool": "ruff",
                "error": {"type": "UnsupportedFile", "message": "Only .py files are supported"}
            })
            
        # Use ruff from the backend virtualenv if available, or globally
        # Because MCP server might be run from backend/.venv, we'll try to just call `ruff`
        # and fallback to a specific path if needed, but standard `ruff` in PATH works if activated.
        # Alternatively, we can use `sys.executable -m ruff`.
        cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json", str(full_path)]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)"""

new_func = """import tempfile
import os
import subprocess

@mcp.tool()
def run_linter(repo_path: str, path: str, revision: str = None) -> str:
    \"\"\"Run a deterministic lint/static-analysis tool against a repository file.
    
    Args:
        repo_path: Absolute path to the local git repository.
        path: File path relative to repository root to lint.
        revision: Optional git revision to lint (e.g. HEAD~1). If omitted, lints working tree.
        
    Returns:
        JSON string containing structured lint issues.
    \"\"\"
    try:
        repo = _validate_repo(repo_path)
        
        # We only support Python files with ruff for now
        if not path.endswith(".py"):
            return json.dumps({
                "path": path,
                "success": False,
                "issues": [],
                "issue_count": 0,
                "tool": "ruff",
                "error": {"type": "UnsupportedFile", "message": "Only .py files are supported"}
            })

        if revision:
            try:
                content = repo.git.show(f"{revision}:{path}")
            except Exception as e:
                # File might not exist in base revision
                return json.dumps({"path": path, "success": True, "issues": [], "issue_count": 0, "tool": "ruff"})
                
            fd, temp_path = tempfile.mkstemp(suffix=".py", prefix="linter_")
            try:
                with os.fdopen(fd, 'w') as f:
                    f.write(content)
                cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json", temp_path]
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)
            finally:
                os.remove(temp_path)
        else:
            full_path = _validate_file_path(repo, path)
            cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json", str(full_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)"""

content = content.replace(old_func, new_func)
content = content.replace("@mcp.tool()\nimport tempfile", "import tempfile")

with open("mcp_server/server.py", "w") as f:
    f.write(content)
