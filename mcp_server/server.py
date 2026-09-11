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


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
