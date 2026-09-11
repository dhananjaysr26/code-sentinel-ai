"""
Schemas for context blocks sent to the LLM reviewer.

A ContextBlock bundles: the diff hunk + surrounding source lines.
ContextBudget controls how much context is included in total.
"""
from pydantic import BaseModel, Field


class ContextBlock(BaseModel):
    """LLM-ready context for one diff hunk.
    
    Contains the raw hunk diff plus surrounding source lines for context.
    This is the unit of input to the correctness reviewer.
    """
    file_path: str
    hunk_new_start: int = Field(description="Starting line of the hunk in new file")
    hunk_new_end: int = Field(description="Ending line of the hunk in new file")
    surrounding_code: str = Field(description="Source lines window around the hunk")
    hunk_diff: str = Field(description="Raw unified diff text for this hunk")
    line_offset: int = Field(
        default=0,
        description="Line number of the first line in surrounding_code (1-indexed)",
    )


class ContextBudget(BaseModel):
    """Controls the total context sent to the LLM.
    
    MVP policy: simple truncation by token count estimate.
    Future: ranked prioritization by change size, call-graph distance, test coverage.
    
    This class is the extension point for future context strategies.
    """
    max_tokens: int = Field(default=8000, description="Total token budget for all context")
    per_file_limit: int = Field(default=3000, description="Per-file token limit")
    window_lines: int = Field(
        default=20,
        description="Lines of surrounding code to include before and after each hunk",
    )
