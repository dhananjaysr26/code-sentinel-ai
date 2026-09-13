#!/usr/bin/env python3
"""
CodeSentinel MCP Server.

Implements the Model Context Protocol (MCP) over stdio transport.
The LangGraph agent calls tools here via the MCP client; it never
reads files or runs git commands directly.

Tools implemented (MVP):
  - get_diff(repo_path, base_ref, target_ref) -> str
  - read_file(repo_path, file_path, start_line, end_line) -> str

Future tools (P1):
  - find_references(repo_path, symbol) -> str
  - run_linter(repo_path, file_path) -> str
  - git_blame(repo_path, file_path, line) -> str

Security:
  - repo_path must be an existing directory containing a .git folder.
  - file_path is validated to not escape the repo_path (path traversal prevention).
  - All subprocess calls use argument lists (no shell=True).
  - Refs are validated before use.
"""
import subprocess
import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("code-sentinel")
except ImportError:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("code-sentinel")


# ── Validation helpers ────────────────────────────────────────────────────────

def _validate_repo(repo_path: str) -> Path:
    """Validate that repo_path is a real git repository.

    Returns:
        Resolved absolute Path to the repository.

    Raises:
        ValueError: If the path is invalid or not a git repo.
    """
    path = Path(repo_path).resolve()
    if not path.exists():
        raise ValueError(f"Repository path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Repository path is not a directory: {path}")
    git_dir = path / ".git"
    if not git_dir.exists():
        # Also accept bare repos or worktrees
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise ValueError(f"Not a git repository: {path}")
    return path


def _validate_ref(repo_path: Path, ref: str) -> None:
    """Validate that a git ref is resolvable.

    Raises:
        ValueError: If the ref does not resolve.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"Invalid git ref: {ref!r}")


def _validate_file_path(repo_path: Path, file_path: str) -> Path:
    """Validate that file_path is within repo_path (prevent path traversal).

    Returns:
        Resolved absolute path to the file.

    Raises:
        ValueError: If the path escapes the repo or does not exist.
    """
    resolved = (repo_path / file_path).resolve()
    try:
        resolved.relative_to(repo_path)
    except ValueError:
        raise ValueError(
            f"File path {file_path!r} escapes repository root {repo_path}"
        )
    if not resolved.exists():
        raise ValueError(f"File does not exist: {resolved}")
    return resolved


def _run_git(cmd: list[str], cwd: Path) -> str:
    """Run a git command and return stdout.

    Raises:
        ValueError: If the command fails.
    """
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise ValueError(
            f"git command {cmd} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


# ── MCP Tools ─────────────────────────────────────────────────────────────────

@mcp.tool()
def get_diff(repo_path: str, base_ref: str, target_ref: str) -> str:
    """Get the unified diff between two git refs in a local repository.

    Args:
        repo_path: Absolute path to the local git repository.
        base_ref:  Base git ref (e.g., HEAD~1, main, a commit SHA).
        target_ref: Target git ref (e.g., HEAD, feature-branch).

    Returns:
        Raw unified diff string. Empty string if no changes.
    """
    try:
        repo = _validate_repo(repo_path)
        _validate_ref(repo, base_ref)
        _validate_ref(repo, target_ref)
        return _run_git(["git", "diff", base_ref, target_ref], cwd=repo)
    except ValueError as exc:
        return f"ERROR: {exc}"


@mcp.tool()
def read_file(repo_path: str, file_path: str, start_line: int, end_line: int) -> str:
    """Read a line range from a file in the repository.

    Lines are 1-indexed and inclusive on both ends.
    Returns fewer lines if end_line exceeds the file length.

    Args:
        repo_path:  Absolute path to the local git repository.
        file_path:  File path relative to repository root.
        start_line: First line to return (1-indexed, inclusive).
        end_line:   Last line to return (1-indexed, inclusive).

    Returns:
        The requested lines as a single string (newline-separated).
    """
    try:
        if start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {start_line}")
        if end_line < start_line:
            raise ValueError(
                f"end_line ({end_line}) must be >= start_line ({start_line})"
            )

        repo = _validate_repo(repo_path)
        full_path = _validate_file_path(repo, file_path)

        content = full_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        actual_end = min(end_line, len(lines))
        selected = lines[start_line - 1 : actual_end]

        # Prepend line numbers to help the LLM identify exact positions
        numbered = [
            f"{start_line + i}: {line}"
            for i, line in enumerate(selected)
        ]
        return "\n".join(numbered)
    except ValueError as exc:
        return f"ERROR: {exc}"


import json
import time

@mcp.tool()
def find_references(repo_path: str, symbol: str, path: str = None) -> str:
    """Find usages/references to a symbol in the configured repository.
    
    Args:
        repo_path: Absolute path to the local git repository.
        symbol: The symbol to search for (function, class, variable, etc).
        path: Optional specific file path to search within. If omitted, searches the whole repository's Python files.
        
    Returns:
        JSON string containing the symbol, a list of references, and the count.
    """
    try:
        if not symbol or not isinstance(symbol, str):
            return json.dumps({"error": "symbol must be a non-empty string"})
        
        repo = _validate_repo(repo_path)
        
        from ast_utils import find_references_in_file
        
        all_refs = []
        if path:
            full_path = _validate_file_path(repo, path)
            rel_path = str(full_path.relative_to(repo))
            if rel_path.endswith(".py"):
                refs = find_references_in_file(str(full_path), symbol)
                for r in refs:
                    r["file"] = rel_path
                all_refs.extend(refs)
        else:
            # Search all Python files
            for p in repo.rglob("*.py"):
                # skip hidden dirs or .venv
                if ".venv" in p.parts or p.name.startswith(".") or any(part.startswith(".") for part in p.parts):
                    continue
                rel_path = str(p.relative_to(repo))
                refs = find_references_in_file(str(p), symbol)
                for r in refs:
                    r["file"] = rel_path
                all_refs.extend(refs)
                
        return json.dumps({
            "symbol": symbol,
            "references": all_refs,
            "count": len(all_refs)
        })
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        return json.dumps({"error": f"Internal error: {exc}"})


import tempfile
import os

@mcp.tool()
def run_linter(repo_path: str, path: str, revision: str = None) -> str:
    """Run a deterministic lint/static-analysis tool against a repository file.
    
    Args:
        repo_path: Absolute path to the local git repository.
        path: File path relative to repository root to lint.
        revision: Optional git ref to lint a specific version.
        
    Returns:
        JSON string containing structured lint issues.
    """
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
            
        import tempfile
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
                os.remove(temp_path)
        
        # ruff check returns 0 if no violations, 1 if violations found, >1 if error
        if result.returncode > 1 and not result.stdout.strip():
            return json.dumps({
                "path": path,
                "success": False,
                "issues": [],
                "issue_count": 0,
                "tool": "ruff",
                "error": {"type": "ExecutionFailed", "message": result.stderr.strip()}
            })
            
        try:
            output_json = json.loads(result.stdout)
        except json.JSONDecodeError:
            # Maybe no issues and empty output, though ruff usually outputs []
            if not result.stdout.strip():
                output_json = []
            else:
                return json.dumps({
                    "path": path,
                    "success": False,
                    "issues": [],
                    "issue_count": 0,
                    "tool": "ruff",
                    "error": {"type": "ParseFailed", "message": "Failed to parse ruff output"}
                })
                
        issues = []
        for item in output_json:
            issues.append({
                "line": item.get("location", {}).get("row"),
                "column": item.get("location", {}).get("column"),
                "code": item.get("code"),
                "severity": "warning",  # ruff doesn't strongly distinguish severity in default json, usually all are issues
                "message": item.get("message")
            })
            
        return json.dumps({
            "path": path,
            "success": True,
            "issues": issues,
            "issue_count": len(issues),
            "tool": "ruff"
        })
        
    except ValueError as exc:
        return json.dumps({
            "path": path,
            "success": False,
            "issues": [],
            "issue_count": 0,
            "tool": "ruff",
            "error": {"type": "ValidationError", "message": str(exc)}
        })
    except Exception as exc:
        return json.dumps({
            "path": path,
            "success": False,
            "issues": [],
            "issue_count": 0,
            "tool": "ruff",
            "error": {"type": "InternalError", "message": str(exc)}
        })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
