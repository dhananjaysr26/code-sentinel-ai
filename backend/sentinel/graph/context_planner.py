import re
from typing import Dict, List, Any
from pydantic import BaseModel, Field

class ContextDecision(BaseModel):
    decision: str
    reason: str

class ReviewScopedEvidence(BaseModel):
    diff: str
    changed_files: List[str] = Field(default_factory=list)
    changed_symbols: List[str] = Field(default_factory=list)
    relevant_code_regions: List[str] = Field(default_factory=list)
    callers_callees: List[str] = Field(default_factory=list)
    relevant_tests: List[str] = Field(default_factory=list)
    context_decisions: Dict[str, ContextDecision] = Field(default_factory=dict)
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)
    
def parse_symbols_from_diff(diff_content: str) -> List[str]:
    """Extremely basic heuristic to find function/class names in diff context/additions."""
    symbols = set()
    for line in diff_content.splitlines():
        # Match python or JS function/class
        m = re.search(r'(?:def|class|function)\s+([A-Za-z0-9_]+)\s*\(?', line)
        if m:
            symbols.add(m.group(1))
    return list(symbols)

def run_context_planner(raw_diff: str, changed_files: List[str]) -> ReviewScopedEvidence:
    """Deterministically plans the context requirements for a code review."""
    symbols = parse_symbols_from_diff(raw_diff)
    
    evidence = ReviewScopedEvidence(
        diff=raw_diff,
        changed_files=changed_files,
        changed_symbols=symbols,
        retrieval_metadata={"planner_execution_time": "deterministic"}
    )
    
    for file in changed_files:
        # Heuristic rules for context decisions
        diff_lines = len(raw_diff.splitlines())
        
        if diff_lines < 30 and len(changed_files) == 1:
            decision = "sufficient_from_diff"
            reason = "Small single-file diff, full context likely visible in diff hunk."
        elif "auth" in file.lower() or "policy" in file.lower() or "permission" in file.lower():
            decision = "requires_cross_file_context"
            reason = "Authorization changes typically require verifying cross-file caller usage."
        else:
            decision = "requires_local_file_context"
            reason = "Medium to large change, requires reading surrounding file logic."
            
        evidence.context_decisions[file] = ContextDecision(
            decision=decision,
            reason=reason
        )
        
    return evidence
