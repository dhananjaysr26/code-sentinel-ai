"""
Pydantic schemas for parsed Git diffs.

The diff parser produces these structures; the LLM never sees raw diff text
directly but sees formatted context blocks derived from these.
"""
from typing import Optional
from pydantic import BaseModel, Field


class DiffHunk(BaseModel):
    """A single contiguous changed region in a file."""
    file_path: str = Field(description="File path relative to repo root")
    old_start: int = Field(description="Starting line in old file")
    old_count: int = Field(description="Number of lines in old file")
    new_start: int = Field(description="Starting line in new file")
    new_count: int = Field(description="Number of lines in new file")
    hunk_text: str = Field(description="Raw unified diff hunk text")
    added_lines: list[str] = Field(default_factory=list, description="Lines added (+)")
    removed_lines: list[str] = Field(default_factory=list, description="Lines removed (-)")
    changed_line_numbers: list[int] = Field(
        default_factory=list,
        description="Line numbers in new file that were added or changed",
    )


class ChangedFile(BaseModel):
    """A file that was modified, added, or deleted in the diff."""
    path: str = Field(description="Target file path relative to repo root")
    old_path: Optional[str] = Field(default=None, description="Original path for renames")
    is_new: bool = Field(default=False)
    is_deleted: bool = Field(default=False)
    hunks: list[DiffHunk] = Field(default_factory=list)


class ParsedDiff(BaseModel):
    """The complete structured representation of a git diff."""
    changed_files: list[ChangedFile] = Field(default_factory=list)
    total_hunks: int = 0
    raw_diff: str = ""
