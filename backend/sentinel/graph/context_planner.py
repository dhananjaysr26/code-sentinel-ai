from __future__ import annotations

import re
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


DecisionType = Literal[
    "sufficient_from_diff",
    "requires_local_file_context",
    "requires_cross_file_context",
]


class ContextDecision(BaseModel):
    decision: DecisionType
    reason: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    risk_signals: List[str] = Field(default_factory=list)
    recommended_tools: List[str] = Field(default_factory=list)


class ReviewUnit(BaseModel):
    id: str
    file: str
    categories: List[str] = Field(default_factory=lambda: ["correctness"])
    diff: str = ""
    changed_lines: List[int] = Field(default_factory=list)
    changed_symbols: List[str] = Field(default_factory=list)
    decision: DecisionType = "requires_local_file_context"
    risk_signals: List[str] = Field(default_factory=list)
    context_budget_tokens: int = 4000


class ReviewScopedEvidence(BaseModel):
    diff: str
    changed_files: List[str] = Field(default_factory=list)
    changed_symbols: List[str] = Field(default_factory=list)
    relevant_code_regions: List[str] = Field(default_factory=list)
    callers_callees: List[str] = Field(default_factory=list)
    relevant_tests: List[str] = Field(default_factory=list)
    context_decisions: Dict[str, ContextDecision] = Field(
        default_factory=dict
    )
    review_units: List[ReviewUnit] = Field(default_factory=list)
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)


SECURITY_PATTERNS = {
    "command_execution": re.compile(
        r"\b(exec|eval|system|popen)\s*\(|\bsubprocess\.",
        re.IGNORECASE,
    ),
    "sql_operation": re.compile(
        r"\b(select|insert|update|delete)\b|"
        r"\b(cursor\.execute|session\.execute|execute)\s*\(",
        re.IGNORECASE,
    ),
    "authorization": re.compile(
        r"\b(authoriz\w*|permission\w*|is_admin|role\w*|"
        r"access_control|privilege\w*)\b",
        re.IGNORECASE,
    ),
    "credential_or_token": re.compile(
        r"\b(password|secret|token|jwt|cookie|api_key)\b",
        re.IGNORECASE,
    ),
    "unsafe_deserialization": re.compile(
        r"\b(pickle\.loads|yaml\.load|deserialize)\s*\(",
        re.IGNORECASE,
    ),
    "filesystem_access": re.compile(
        r"\b(open|readFile|writeFile|unlink|remove)\s*\(",
        re.IGNORECASE,
    ),
}

CORRECTNESS_PATTERNS = {
    "boundary_or_index": re.compile(
        r"\b(length|index|offset|range|slice)\b|"
        r"(?<![=!])==(?!=)|(?<![=!])!=(?!=)|<=|>=",
        re.IGNORECASE,
    ),
    "nullable_value": re.compile(
        r"\b(None|null|undefined|optional|nullable)\b",
        re.IGNORECASE,
    ),
    "resource_lifecycle": re.compile(
        r"\b(open|close|dispose|release|finally|with)\b",
        re.IGNORECASE,
    ),
    "numeric_logic": re.compile(
        r"\b(float|double|Decimal|money|amount|price|total)\b",
        re.IGNORECASE,
    ),
    "concurrency": re.compile(
        r"\b(async|await|thread|lock|mutex|race|transaction)\b",
        re.IGNORECASE,
    ),
}

CROSS_FILE_PATTERNS = {
    "public_symbol": re.compile(
        r"\b(export|import|from|def|function|class|public)\b",
        re.IGNORECASE,
    ),
    "api_or_contract": re.compile(
        r"\b(api|route|router|endpoint|schema|model|response|request)\b",
        re.IGNORECASE,
    ),
    "configuration": re.compile(
        r"\b(config|settings|environment|env|migration)\b",
        re.IGNORECASE,
    ),
}


def split_diff_by_file(raw_diff: str) -> Dict[str, str]:
    """
    Split a unified Git diff into file-scoped sections.

    This intentionally handles ordinary Git diff output and avoids
    relying on blank-line formatting.
    """
    sections: Dict[str, List[str]] = {}
    current_file: str | None = None

    for line in raw_diff.splitlines():
        if line.startswith("diff --git "):
            match = re.match(
                r"diff --git a/(.*?) b/(.*)$",
                line,
            )

            if match:
                current_file = match.group(2)
                sections[current_file] = [line]
            else:
                current_file = None

            continue

        if current_file is not None:
            sections[current_file].append(line)

    return {
        path: "\n".join(lines)
        for path, lines in sections.items()
    }


def extract_changed_lines(file_diff: str) -> List[int]:
    """
    Extract approximate new-file line numbers from unified diff hunks.
    """
    changed_lines: List[int] = []
    current_line = 0

    for line in file_diff.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                current_line = int(match.group(1))
            continue

        if line.startswith("+++"):
            continue

        if line.startswith("+"):
            changed_lines.append(current_line)
            current_line += 1
        elif line.startswith("-"):
            # Removed lines do not advance the new-file line number.
            continue
        else:
            current_line += 1

    return changed_lines


def parse_symbols_from_diff(diff_content: str) -> List[str]:
    """
    Lightweight symbol extraction.

    This is intentionally heuristic, not a full language parser.
    """
    patterns = [
        r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\basync\s+def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=",
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
    ]

    symbols = set()

    for line in diff_content.splitlines():
        # Focus on changed or context lines, excluding diff metadata.
        if line.startswith(("diff --git", "index ", "---", "+++")):
            continue

        for pattern in patterns:
            for match in re.finditer(pattern, line):
                symbols.add(match.group(1))

    return sorted(symbols)


def calculate_signals(
    file_path: str,
    file_diff: str,
) -> tuple[List[str], List[str], Dict[str, int]]:
    text = f"{file_path}\n{file_diff}"

    risk_signals: List[str] = []
    categories = ["correctness"]
    scores = {
        "security": 0,
        "correctness": 0,
        "cross_file": 0,
    }

    for signal, pattern in SECURITY_PATTERNS.items():
        if pattern.search(text):
            risk_signals.append(signal)
            if signal == "command_execution":
                scores["security"] += 3
            elif signal == "sql_operation":
                scores["security"] += 2
            elif signal == "authorization":
                scores["security"] += 2
            else:
                scores["security"] += 1

    for signal, pattern in CORRECTNESS_PATTERNS.items():
        if pattern.search(text):
            risk_signals.append(signal)
            scores["correctness"] += 1

    for signal, pattern in CROSS_FILE_PATTERNS.items():
        if pattern.search(text):
            risk_signals.append(signal)
            scores["cross_file"] += 1

    if scores["security"] > 0:
        categories.append("security")

    return sorted(set(categories)), sorted(set(risk_signals)), scores


def decide_context(
    file_path: str,
    file_diff: str,
    changed_files_count: int,
    changed_lines_count: int,
    risk_signals: List[str],
    scores: Dict[str, int],
) -> ContextDecision:
    is_small = (
        changed_files_count == 1
        and changed_lines_count <= 25
    )

    has_security_risk = scores["security"] >= 1
    has_cross_file_risk = scores["cross_file"] >= 2
    has_complexity_risk = scores["correctness"] >= 3

    if has_security_risk and (
        scores["security"] >= 2 or has_cross_file_risk
    ):
        return ContextDecision(
            decision="requires_cross_file_context",
            reason=(
                "The diff contains security-sensitive behavior and may "
                "depend on callers, validation, or authorization policy."
            ),
            confidence=0.9,
            risk_signals=risk_signals,
            recommended_tools=[
                "read_file",
                "find_references",
            ],
        )

    if has_cross_file_risk:
        return ContextDecision(
            decision="requires_cross_file_context",
            reason=(
                "The change may affect an API, public symbol, configuration, "
                "or contract used outside the changed file."
            ),
            confidence=0.82,
            risk_signals=risk_signals,
            recommended_tools=[
                "read_file",
                "find_references",
            ],
        )

    if is_small and not has_complexity_risk and not has_security_risk:
        return ContextDecision(
            decision="sufficient_from_diff",
            reason=(
                "Small, single-file, low-risk change with no detected "
                "cross-file or security-sensitive signals."
            ),
            confidence=0.75,
            risk_signals=risk_signals,
            recommended_tools=[],
        )

    return ContextDecision(
        decision="requires_local_file_context",
        reason=(
            "The diff may be understandable locally, but additional "
            "surrounding code is needed to verify behavior safely."
        ),
        confidence=0.78,
        risk_signals=risk_signals,
        recommended_tools=["read_file"],
    )


def run_context_planner(
    raw_diff: str,
    changed_files: List[str],
) -> ReviewScopedEvidence:
    file_diffs = split_diff_by_file(raw_diff)

    all_symbols = sorted(set(parse_symbols_from_diff(raw_diff)))

    evidence = ReviewScopedEvidence(
        diff=raw_diff,
        changed_files=changed_files,
        changed_symbols=all_symbols,
        retrieval_metadata={
            "planner": "deterministic",
            "planner_version": "2",
            "file_count": len(changed_files),
        },
    )

    for index, file_path in enumerate(changed_files, start=1):
        file_diff = file_diffs.get(file_path, raw_diff)
        changed_lines = extract_changed_lines(file_diff)

        categories, risk_signals, scores = calculate_signals(
            file_path,
            file_diff,
        )

        symbols = parse_symbols_from_diff(file_diff)

        decision = decide_context(
            file_path=file_path,
            file_diff=file_diff,
            changed_files_count=len(changed_files),
            changed_lines_count=len(changed_lines),
            risk_signals=risk_signals,
            scores=scores,
        )

        evidence.context_decisions[file_path] = decision

        evidence.review_units.append(
            ReviewUnit(
                id=f"unit-{index}",
                file=file_path,
                categories=categories,
                diff=file_diff,
                changed_lines=changed_lines,
                changed_symbols=symbols,
                decision=decision.decision,
                risk_signals=risk_signals,
                context_budget_tokens=(
                    2500
                    if decision.decision == "sufficient_from_diff"
                    else 5000
                    if decision.decision == "requires_local_file_context"
                    else 7000
                ),
            )
        )

    return evidence
