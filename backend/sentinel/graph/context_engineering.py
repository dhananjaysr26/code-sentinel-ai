import uuid
import json
import re
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage, SystemMessage

class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reviewer: str
    source: str
    path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    symbol: Optional[str] = None
    evidence_type: str
    summary: str
    content: str
    relevance: str = "medium"
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class TokenBudgets(BaseModel):
    max_diff_tokens: int = 10000
    max_context_tokens: int = 20000
    max_evidence_items: int = 20
    max_lines_per_evidence: int = 200
    max_mcp_calls_per_reviewer: int = 5
    max_llm_iterations_per_reviewer: int = 5

def generate_evidence_cache_key(commit_sha: str, tool_name: str, args: dict) -> str:
    """Cache key includes commit SHA to invalidate across revisions."""
    args_json = json.dumps(args, sort_keys=True)
    return f"{commit_sha}:{tool_name}:{args_json}"

def normalize_evidence(tool_name: str, args: dict, result: str, reviewer: str) -> EvidenceItem:
    """Deterministically normalizes raw tool output into a structured EvidenceItem."""
    path = args.get("file_path", "")
    if not path and "symbol" in args:
        path = "symbol_search"
    line_start = args.get("start_line")
    line_end = args.get("end_line")
    symbol = args.get("symbol")
    
    if tool_name == "read_file":
        summary = f"Read {path}"
        if line_start and line_end:
            summary += f" lines {line_start}-{line_end}"
        evidence_type = "code_snippet"
    elif tool_name == "find_references":
        summary = f"Found references for '{symbol}'"
        evidence_type = "reference_list"
    else:
        summary = f"Executed {tool_name}"
        evidence_type = "tool_output"
        
    return EvidenceItem(
        reviewer=reviewer,
        source=tool_name,
        path=path,
        line_start=line_start,
        line_end=line_end,
        symbol=symbol,
        evidence_type=evidence_type,
        summary=summary,
        content=result
    )

def generate_context_manifest(evidence_store: List[EvidenceItem], reviewer: str = None, include_content: bool = False) -> str:
    """Generates a compact summary of retrieved evidence to inject into LLM prompt."""
    if not evidence_store:
        return "No additional evidence retrieved yet."
    
    lines = ["### COMPACT CONTEXT MANIFEST"]
    for ev in evidence_store:
        if reviewer and ev.reviewer != reviewer:
            continue
        loc = f"{ev.path}"
        if ev.line_start and ev.line_end:
            loc += f" (lines {ev.line_start}-{ev.line_end})"
        if ev.symbol:
            loc += f" [symbol: {ev.symbol}]"
        
        lines.append(f"- ID: {ev.evidence_id} | {loc} | {ev.summary}")
        if include_content:
            lines.append("```")
            lines.append(ev.content)
            lines.append("```")
            
    if not include_content:
        lines.append("\n(Raw content stored in evidence_store. Re-fetch via MCP only if new details are needed).")
    return "\n".join(lines)

def relevance_aware_compaction(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Compacts messages by keeping:
    - Initial task (System, Human)
    - Replaces all ToolMessages with placeholders, as their content is injected via Context Manifest.
    """
    if len(messages) <= 2:
        return messages
        
    compacted = []
    # Always keep system and initial user message
    compacted.append(messages[0])
    compacted.append(messages[1])
    
    for msg in messages[2:]:
        if isinstance(msg, ToolMessage):
            compact_msg = ToolMessage(
                content="[CONTENT COMPACTED - Recorded in Context Manifest above]",
                tool_call_id=msg.tool_call_id,
                name=msg.name
            )
            compacted.append(compact_msg)
        else:
            compacted.append(msg)
            
    return compacted

def compute_token_breakdown(messages: List[BaseMessage]) -> Dict[str, int]:
    """Estimates the token count of various context sections for instrumentation."""
    breakdown = {
        "system_prompt_tokens": 0,
        "diff_tokens": 0,
        "history_tokens": 0,
        "tool_result_tokens": 0,
    }
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        tokenize = lambda x: len(enc.encode(str(x))) if x else 0
    except ImportError:
        tokenize = lambda x: len(str(x)) // 4 if x else 0

    if not messages:
        return breakdown

    # System prompt
    if isinstance(messages[0], SystemMessage):
        breakdown["system_prompt_tokens"] = tokenize(messages[0].content)

    # Initial Diff
    if len(messages) > 1 and isinstance(messages[1], HumanMessage):
        breakdown["diff_tokens"] = tokenize(messages[1].content)
        
    # Tool Results and History
    for msg in messages[2:]:
        tokens = tokenize(msg.content)
        if isinstance(msg, ToolMessage):
            breakdown["tool_result_tokens"] += tokens
        else:
            breakdown["history_tokens"] += tokens
            
    return breakdown
