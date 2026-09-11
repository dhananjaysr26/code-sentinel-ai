"""
Pydantic schemas for code review findings.

Designed for stability: new sources and categories can be added
without breaking existing findings.
"""
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    """How severe the issue is if it occurs."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Category(str, Enum):
    """Which type of reviewer produced this finding.

    Phase 1: CORRECTNESS + SECURITY (parallel reviewers).
    Future: PERFORMANCE, STYLE.
    """
    CORRECTNESS = "correctness"
    SECURITY = "security"
    CODE_QUALITY = "code_quality"
    NUMERIC_BUSINESS_LOGIC = "numeric_business_logic"
    CONCURRENCY = "concurrency"


class Source(str, Enum):
    """What produced the finding.
    
    MVP: LLM only.
    Future: LINTER (deterministic), AST (static analysis).
    """
    LLM = "llm"
    LINTER = "linter"
    AST = "ast"


class Finding(BaseModel):
    """A single code review finding.
    
    All fields except id, suggested_fix, and line are required.
    This schema is the contract between the LangGraph pipeline and the frontend.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file: str = Field(description="File path relative to repo root")
    line: Optional[int] = Field(default=None, description="Line number in target file (1-indexed)")
    title: str = Field(description="Short, specific title of the issue")
    category: Category
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0, description="Reviewer confidence 0.0-1.0")
    explanation: str = Field(description="Why this is a bug, with reference to the code")
    evidence: str = Field(description="The specific code snippet that demonstrates the issue")
    suggested_fix: Optional[str] = Field(default=None, description="Concrete fix suggestion")
    source: Source = Field(default=Source.LLM)
    # Phase 2 fields — optional for full backward compatibility
    subcategory: Optional[str] = Field(
        default=None,
        description="Fine-grained subcategory, e.g. 'sql_injection', 'off_by_one'",
    )
    reviewer: Optional[str] = Field(
        default=None,
        description="Which reviewer node produced this: 'correctness' or 'security'",
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 3 decimal places for consistency."""
        return round(v, 3)

    @field_validator("file")
    @classmethod
    def normalize_file_path(cls, v: str) -> str:
        """Strip leading slash or ./ from file paths for consistency."""
        return v.lstrip("./").lstrip("/")


class ReviewFindings(BaseModel):
    """Container returned by the correctness reviewer.
    
    The LLM is constrained to produce this exact schema via structured output.
    If no issues are found, findings is an empty list.
    """
    findings: list[Finding] = Field(default_factory=list)
