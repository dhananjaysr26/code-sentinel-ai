"""
Git service: safe, validated access to a local Git repository.

All subprocess calls use argument lists (never shell=True with string interpolation)
to prevent command injection. Repository paths and refs are validated before use.
"""
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitServiceError(Exception):
    """Raised when a Git operation fails in an unexpected way."""


class GitService:
    """Provides validated, safe Git operations against a single repository.
    
    Design: one GitService instance per review request. All operations
    are scoped to self.repo_path and use subprocess argument lists.
    """

    def __init__(self, repo_path: str | Path) -> None:
        """Initialize and validate that repo_path is a git repository.
        
        Args:
            repo_path: Path to the local git repository.
            
        Raises:
            ValueError: If the path does not exist or is not a git repository.
        """
        self.repo_path: Path = Path(repo_path).resolve()

        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        if not self.repo_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {self.repo_path}")

        # Verify it's a git repo
        result = self._run(["git", "rev-parse", "--is-inside-work-tree"], check=False)
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise ValueError(
                f"Not a git repository (or not inside one): {self.repo_path}"
            )

        logger.debug("GitService initialized for %s", self.repo_path)

    def validate_ref(self, ref: str) -> bool:
        """Check whether a ref (branch, tag, commit SHA, HEAD~N) is valid.
        
        Args:
            ref: A git ref string.
            
        Returns:
            True if the ref resolves to a commit, False otherwise.
            
        Raises:
            GitServiceError: On unexpected subprocess failure.
        """
        result = self._run(["git", "rev-parse", "--verify", ref], check=False)
        if result.returncode == 0:
            return True
        if result.returncode == 128:
            # Expected: ref does not exist
            return False
        # Unexpected failure
        raise GitServiceError(
            f"Unexpected error validating ref {ref!r}: {result.stderr.strip()}"
        )

    def get_diff(self, base_ref: str, target_ref: str) -> str:
        """Get the unified diff between two refs.
        
        Args:
            base_ref: The base git ref.
            target_ref: The target git ref.
            
        Returns:
            Raw unified diff string (may be empty if no changes).
            
        Raises:
            GitServiceError: If the git command fails.
        """
        result = self._run(
            ["git", "diff", base_ref, target_ref],
            check=False,
        )
        if result.returncode not in (0, 1):
            # git diff exits 1 when there ARE differences (not an error)
            # Any other non-zero exit is an error
            raise GitServiceError(
                f"git diff failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout

    def get_changed_files(self, base_ref: str, target_ref: str) -> list[str]:
        """Get list of files changed between two refs.
        
        Returns:
            List of file paths relative to repo root.
        """
        result = self._run(
            ["git", "diff", "--name-only", base_ref, target_ref],
            check=True,
        )
        files = [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
        return files

    def read_file_at_ref(self, file_path: str, ref: str = "HEAD") -> str:
        """Read a file's content at a specific git ref.
        
        Args:
            file_path: Path relative to repo root.
            ref: Git ref (default: HEAD).
            
        Returns:
            File content as string.
            
        Raises:
            GitServiceError: If the file cannot be read at that ref.
        """
        result = self._run(
            ["git", "show", f"{ref}:{file_path}"],
            check=False,
        )
        if result.returncode != 0:
            raise GitServiceError(
                f"Cannot read {file_path!r} at {ref!r}: {result.stderr.strip()}"
            )
        return result.stdout

    def read_file_lines(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """Read a range of lines from a file in the working tree.
        
        Args:
            file_path: Path relative to repo root.
            start_line: First line to return (1-indexed, inclusive).
            end_line: Last line to return (1-indexed, inclusive).
            
        Returns:
            The requested lines joined as a string.
            
        Raises:
            ValueError: If line range is invalid.
            GitServiceError: If the file cannot be read.
        """
        if start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {start_line}")
        if end_line < start_line:
            raise ValueError(
                f"end_line ({end_line}) must be >= start_line ({start_line})"
            )

        full_path = self.repo_path / file_path
        # Verify the file doesn't escape the repo root
        try:
            full_path.resolve().relative_to(self.repo_path)
        except ValueError:
            raise GitServiceError(
                f"File path {file_path!r} escapes repository root"
            )

        if not full_path.exists():
            raise GitServiceError(f"File not found in working tree: {file_path}")

        lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        # Clamp to actual file length
        actual_end = min(end_line, len(lines))
        selected = lines[start_line - 1 : actual_end]
        return "\n".join(selected)

    def _run(
        self,
        cmd: list[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a git command in the repository directory.
        
        Args:
            cmd: Command as argument list (no shell interpolation).
            check: If True, raise CalledProcessError on non-zero exit.
            
        Returns:
            CompletedProcess with stdout/stderr as strings.
        """
        try:
            return subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=check,
            )
        except subprocess.CalledProcessError as exc:
            raise GitServiceError(
                f"Command {cmd} failed (exit {exc.returncode}): {exc.stderr.strip()}"
            ) from exc
        except FileNotFoundError:
            raise GitServiceError(
                "git executable not found. Is git installed and on PATH?"
            )
