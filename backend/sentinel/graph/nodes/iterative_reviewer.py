"""
Iterative MCP-enabled reviewer loop.

This module provides run_iterative_reviewer(), a bounded async loop that
replaces the single invoke_structured() call inside each specialist reviewer.

Loop lifecycle per specialist:
    STEP 1 — Initial LLM call with tools bound (NOT with_structured_output).
    STEP 2 — Inspect response:
              A) tool_calls present  → execute via MCP, append result, loop back
              B) text content        → extract JSON findings, done
              C) JSON parse failure  → one structured-output repair call, done
              D) provider error      → record stop_reason='error', done
    STEP 6 — Terminate when any hard limit is reached.

Hard limits (all configurable via settings / env vars):
    ITERATIVE_MAX_ITERATIONS          (default 3)
    ITERATIVE_MAX_TOOL_CALLS          (default 5)
    ITERATIVE_REVIEW_TIMEOUT_SECONDS  (default 45)
    ITERATIVE_MAX_TOOL_RESULT_CHARS   (default 12000)
    ITERATIVE_MAX_REPEATED_TOOL_CALLS (default 1)

Duplicate-call detection:
    Key = tool_name + JSON-sorted(args)
    A key already in executed_keys → stop_reason='duplicate_tool_call'
"""
import json
import logging
import re
import time
from typing import Any
from uuid import uuid4

from django.conf import settings
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), reraise=True)
async def safe_ainvoke(llm, messages):
    return await llm.ainvoke(messages)

from sentinel.schemas.findings import ReviewFindings
from sentinel.services.llm_service import invoke_structured, get_llm, _normalize_usage
from sentinel.graph.context_engineering import (
    compute_token_breakdown,
    normalize_evidence,
    generate_context_manifest,
    relevance_aware_compaction,
    generate_evidence_cache_key,
    EvidenceItem
)


logger = logging.getLogger(__name__)


# ── MCP Tool definitions sent to the LLM via bind_tools() ─────────────────────
MCP_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a specific file and optional line range from the target repository.\n"
                "Use this when:\n"
                "- A changed function depends on a definition not included in the current context.\n"
                "- A caller, callee, type, test, or error-handling path is missing.\n"
                "- Additional code could change the review conclusion.\n"
                "Rules:\n"
                "- Do not reread content already present in the conversation.\n"
                "- Prefer a narrow line range when the relevant location is known.\n"
                "- Do not use this for broad repository exploration."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path from repo root, e.g. 'src/policy.py'",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed). Default 1.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (inclusive). Default 200.",
                    },
                    "justification": {
                        "type": "string",
                        "description": "Why do you need to read this file? What specific information are you looking for?",
                    }
                },
                "required": ["file_path", "justification"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_references",
            "description": (
                "Find references to a symbol in the target repository.\n"
                "Use this when:\n"
                "- A changed symbol's callers or callees affect correctness or security.\n"
                "- You need to determine how a changed behavior propagates.\n"
                "- You need to verify whether an authorization or validation function is used elsewhere.\n"
                "Rules:\n"
                "- Do not use this for general repository exploration.\n"
                "- Do not repeat the same symbol lookup unless the search scope differs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The exact function, class, or variable name.",
                    },
                    "justification": {
                        "type": "string",
                        "description": "Why do you need to find this symbol? What specific information are you looking for?",
                    }
                },
                "required": ["symbol", "justification"],
            },
        },
    },
]

# ── Specialist system prompts ──────────────────────────────────────────────────
_SECURITY_SYSTEM_PROMPT = """\
You are a senior security code reviewer with access to MCP tools.

PHASE 1: INVESTIGATION
- Inspect EVERY changed file and EVERY changed hunk.
- Analyze the supplied diff and initial context first.
- Use MCP ONLY when a concrete unresolved question may affect the review.
- Incorporate every tool result into the next reasoning step.
- Avoid retrieving content already provided. Avoid repeating identical tool calls.
- Continue reviewing ALL changed hunks after finding an issue.
- Do NOT produce final structured findings during the investigation phase.

SYSTEMATIC COVERAGE REQUIRED:
7. Authentication and authorization
8. Injection and unsafe data flow

TOOL-USAGE POLICY:
Before requesting a tool, identify the concrete uncertainty it resolves.
- read_file: Use when a definition/caller/type is missing and could change the conclusion. Do NOT reread content already present. Prefer narrow line ranges.
- find_references: Use when a changed symbol's usage affects correctness/security. Do NOT repeat the same lookup.

PHASE 2: FINALIZATION
(You will be explicitly instructed when this phase begins).
- Reassess every changed file and hunk.
- Incorporate all retrieved context.
- Confirm or reject candidate findings. Remove speculative findings and duplicate root causes.
- Every finding must include a concrete changed-line anchor (never null).
"""

_CORRECTNESS_SYSTEM_PROMPT = """\
You are a senior correctness code reviewer with access to MCP tools.

PHASE 1: INVESTIGATION
- Inspect EVERY changed file and EVERY changed hunk.
- Analyze the supplied diff and initial context first.
- Use MCP ONLY when a concrete unresolved question may affect the review.
- Incorporate every tool result into the next reasoning step.
- Avoid retrieving content already provided. Avoid repeating identical tool calls.
- Continue reviewing ALL changed hunks after finding an issue.
- Do NOT produce final structured findings during the investigation phase.

SYSTEMATIC COVERAGE REQUIRED:
1. Correctness and business logic
2. Boundary conditions and off-by-one errors
3. Null/None/undefined handling
4. Error handling and exception behavior
5. Resource cleanup and lifecycle management
6. Input validation
9. API and backward compatibility
10. Concurrency and state consistency
11. Test impact

TOOL-USAGE POLICY:
Before requesting a tool, identify the concrete uncertainty it resolves.
- read_file: Use when a definition/caller/type is missing and could change the conclusion. Do NOT reread content already present. Prefer narrow line ranges.
- find_references: Use when a changed symbol's usage affects correctness/security. Do NOT repeat the same lookup.

PHASE 2: FINALIZATION
(You will be explicitly instructed when this phase begins).
- Reassess every changed file and hunk.
- Incorporate all retrieved context.
- Confirm or reject candidate findings. Remove speculative findings and duplicate root causes.
- Every finding must include a concrete changed-line anchor (never null).
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _tool_call_key(tool_name: str, args: dict) -> str:
    """Normalize a tool call to a deduplication key."""
    return f"{tool_name}:{json.dumps(args, sort_keys=True)}"


def _parse_findings_from_text(text: str, specialist: str) -> list | None:
    """Attempt to extract a findings list from raw LLM text.

    Returns:
        list of finding dicts if parsing succeeds,
        None if no valid JSON could be found.
    """
    if not text:
        return None
    # Prefer a fenced JSON block, fall back to first {...} blob
    json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if not json_match:
        json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        return None
    try:
        raw_json = json_match.group(1) if json_match.lastindex else json_match.group()
        data = json.loads(raw_json)
        if "findings" not in data:
            return None
        findings = data.get("findings", [])
        for f in findings:
            f.setdefault("reviewer", specialist)
            f.setdefault("source", "llm")
        return findings
    except Exception as e:
        logger.warning("Failed to parse findings json: %s", e)
        return None


async def _execute_tool(mcp_client, tool_name: str, args: dict, repo_path: str) -> str:
    """Execute one MCP tool call. Returns tool output or an error string."""
    MAX_CHARS = getattr(settings, "ITERATIVE_MAX_TOOL_RESULT_CHARS", 12000)

    if tool_name == "read_file":
        file_path = args.get("file_path", "")
        # Security: reject path traversal
        if ".." in file_path or file_path.startswith("/"):
            return "ERROR: Invalid file path — path traversal is not permitted."
        start_line = max(1, int(args.get("start_line", 1)))
        end_line = max(start_line, int(args.get("end_line", 200)))
        result = await mcp_client.read_file(repo_path, file_path, start_line, end_line)
        if len(result) > MAX_CHARS:
            result = result[:MAX_CHARS] + "\n... [TRUNCATED — file exceeded max context size]"
        return result

    elif tool_name == "find_references":
        symbol = args.get("symbol", "")
        if not symbol:
            return "ERROR: 'symbol' argument is required."
        result = await mcp_client.find_references(repo_path, symbol)
        if len(result) > MAX_CHARS:
            result = result[:MAX_CHARS] + "\n... [TRUNCATED]"
        return result

    return f"ERROR: Unknown tool {tool_name!r}. Available: read_file, find_references."


def _get_model_name(llm) -> str:
    """Extract model name from LangChain LLM object."""
    for attr in ("model_id", "model_name", "model"):
        val = getattr(llm, attr, None)
        if val:
            return str(val)
    return "unknown"


# ── Main iterative loop ────────────────────────────────────────────────────────

def _compress_message_history(messages: list) -> None:
    """Selective context management for LangChain/LangGraph agents.
    
    Compresses older ToolMessages to save tokens while keeping the most
    recent interaction uncompressed. Never blindly deletes history, as the
    LLM needs it for multi-hop reasoning.
    """
    if not messages:
        return
        
    # Find the indices of all ToolMessages
    tool_msg_indices = [i for i, msg in enumerate(messages) if getattr(msg, "type", "") == "tool" or isinstance(msg, ToolMessage)]
    
    if len(tool_msg_indices) <= 2:
        # Not enough history to compress
        return
        
    # Keep the last 2 tool messages uncompressed
    indices_to_compress = tool_msg_indices[:-2]
    
    for idx in indices_to_compress:
        msg = messages[idx]
        if hasattr(msg, "content") and isinstance(msg.content, str):
            if len(msg.content) > 1000:
                # Keep the first 300 and last 300 chars, heavily summarize the middle
                start = msg.content[:300]
                end = msg.content[-300:]
                msg.content = f"{start}\n\n... [CONTENT COMPRESSED (saved {len(msg.content)} chars) - Original available via tool re-fetch if strictly needed] ...\n\n{end}"

async def run_iterative_reviewer(
    specialist: str,
    state: dict,
    provider: str,
    repo_path: str,
    mcp_client,
) -> dict:
    """Bounded iterative MCP-enabled reviewer loop.

    Args:
        specialist: 'correctness' or 'security'.
        state:      The current LangGraph ReviewState dict.
        provider:   'bedrock' or 'openai'.
        repo_path:  Absolute path to the target repository.
        mcp_client: MCPClientInterface instance.

    Returns:
        Partial state dict with keys:
          - '{specialist}_raw_findings'
          - 'llm_usages'
          - 'reviewer_latencies'
          - 'errors' or 'security_errors' (only on error)
    """
    MAX_ITERATIONS = getattr(settings, "ITERATIVE_MAX_ITERATIONS", 3)
    MAX_TOOL_CALLS = getattr(settings, "ITERATIVE_MAX_TOOL_CALLS", 3)
    MAX_TIMEOUT = getattr(settings, "ITERATIVE_REVIEW_TIMEOUT_SECONDS", 45)

    review_start = time.monotonic()
    executed_keys: set[str] = set()
    iteration = 0
    mcp_calls = 0
    unique_mcp_calls = 0
    duplicate_mcp_calls = 0
    retry_count = 0
    fallback_count = 0
    timeout_count = 0
    llm_latency_ms = 0
    mcp_latency_ms = 0
    
    tool_call_count = 0
    llm_call_count = 0
    tools_used: list[str] = []
    context_files: list[str] = []
    new_usages: list[dict] = []   # only usages from THIS specialist (reducer will combine)
    stop_reason = "unknown"
    findings: list[dict] = []
    force_final_next = False
    review_id = state.get("metadata", {}).get("review_id", "?")
    blocks = state.get("context_blocks", [])
    
    # We share a cache among parallel reviewers via state
    tool_cache = state.get("tool_cache", {})
    evidence_store = state.get("evidence_store", [])
    # For cache keying, we need the repo SHA or at least the target_ref
    cache_ref = state.get("target_ref", "HEAD")

    logger.info(
        "REVIEW_LOOP_START specialist=%s review_id=%s context_blocks=%d",
        specialist, review_id, len(blocks),
    )

    # Build initial messages
    system_prompt = (
        _SECURITY_SYSTEM_PROMPT if specialist == "security" else _CORRECTNESS_SYSTEM_PROMPT
    )
    human_content = "### REVIEW METADATA\n"
    human_content += f"- Repository: {state.get('repo_path', 'unknown').split('/')[-1]}\n"
    human_content += f"- Base revision: {state.get('base_ref', 'unknown')}\n"
    human_content += f"- Target revision: {state.get('target_ref', 'unknown')}\n"
    human_content += f"- Review specialist: {specialist}\n"
    human_content += f"- Review phase: investigation\n\n"
    
    changed_files = state.get("changed_files", [])
    if changed_files:
        human_content += "### CHANGED FILES\n"
        for cf in changed_files:
            human_content += f"- {cf.path}\n"
        human_content += "\n"
        
    human_content += "### ALREADY AVAILABLE CONTEXT\n"
    for block in blocks:
        # We don't track explicit line ranges in block right now, but we can list the file
        human_content += f"- {block.file_path}: (loaded around changed hunks)\n"
    human_content += "\n"
    
    human_content += "### RULES\n"
    human_content += "- Do not request content already included in the current context.\n"
    human_content += "- Use MCP only for missing context that may change the review conclusion.\n"
    human_content += "- Prefer narrow retrieval when the relevant location is known.\n\n"
    
    human_content += "### INITIAL CODE CHANGES\n\n"
    for block in blocks:
        human_content += f"File: {block.file_path}\n"
        human_content += f"```python\n{block.surrounding_code}\n```\n"
        human_content += f"Diff:\n```diff\n{block.hunk_diff}\n```\n\n"

    messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]

    llm = get_llm(provider)
    evidence_package = state.get("evidence_package", {})
    context_decisions = evidence_package.get("context_decisions", {})
    raw_diff = state.get("raw_diff", "")
    
    all_sufficient = False
    if context_decisions:
        all_sufficient = all(d.get("decision") == "sufficient_from_diff" for d in context_decisions.values())
    elif not context_decisions and raw_diff and len(raw_diff.splitlines()) < 100:
        all_sufficient = True
        
    if all_sufficient:
        logger.info("SPECIALIST_FAST_PATH specialist=%s — context is sufficient_from_diff. Bypassing tool loop.", specialist)
        t_final = time.monotonic()
        manifest = generate_context_manifest(evidence_store, specialist, include_content=True)
        final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\n\n{manifest}\n\nNote: The Diff was marked as sufficient. Please analyze the diff directly."
        final_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_content),
            HumanMessage(content=final_package_prompt)
        ]
        
        try:
            structured_result = await invoke_structured(provider, final_messages, ReviewFindings)
            r_latency = int((time.monotonic() - t_final) * 1000)
            
            s_dict = structured_result.usage.model_dump() if structured_result.usage else {}
            s_dict["reviewer"] = specialist
            s_dict["iteration"] = 0
            s_dict["llm_call_number"] = 1
            s_dict.update(compute_token_breakdown(final_messages))
            
            final_findings = []
            if structured_result.response:
                for f in structured_result.response.findings:
                    d = f.model_dump()
                    d["reviewer"] = specialist
                    d.setdefault("source", "llm")
                    final_findings.append(d)
                    
            existing_latencies = dict(state.get("reviewer_latencies", {}))
            existing_latencies[f"{specialist}_ms"] = r_latency
            existing_latencies[f"{specialist}_loop"] = {
                "specialist_name": specialist,
                "llm_call_count": 1,
                "tool_call_count": 0,
                "iteration_count": 0,
                "tools_used": [],
                "context_files_retrieved": [],
                "stop_reason": "sufficient_from_diff_fast_path",
                "total_latency_ms": r_latency,
                "finding_count": len(final_findings)
            }
            
            return {
                f"{specialist}_raw_findings": final_findings,
                "llm_usages": [s_dict],
                "reviewer_latencies": existing_latencies,
                "timeline": [{"node": specialist, "event": "llm_call", "details": "invoke_structured (fast_path)", "latency_ms": r_latency, "tokens": s_dict.get("total_tokens", 0)}],
                "llm_latency_ms": r_latency,
                "mcp_calls": 0,
                "unique_mcp_calls": 0,
                "duplicate_mcp_calls": 0,
                "agent_iterations": 0,
                "retry_count": 0,
                "fallback_count": 0,
                "timeout_count": 0,
                "mcp_latency_ms": 0,
            }
        except Exception as exc:
            logger.error("Fast path structured extraction failed: %s", exc)


    model_name = _get_model_name(llm)

    # ── Main loop ──────────────────────────────────────────────────────────────
    new_timeline = []
    
    review_id = state.get("metadata", {}).get("review_id", "")
    def _add_event(event_dict):
        new_timeline.append(event_dict)
        if review_id:
            from datetime import datetime, timezone
            try:
                from sentinel.services.events import publish_event
                sse_event = {
                    "review_id": review_id,
                    "reviewer": specialist,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **event_dict
                }
                publish_event(review_id, sse_event)
            except ImportError:
                pass
                
    while iteration < MAX_ITERATIONS:
        # Timeout guard
        elapsed = time.monotonic() - review_start
        if elapsed > MAX_TIMEOUT:
            stop_reason = "timeout"
            timeout_count += 1
            logger.warning(
                "SPECIALIST_LOOP_STOP reason=timeout specialist=%s elapsed_s=%.1f",
                specialist, elapsed,
            )
            break

        iteration += 1
        llm_call_count += 1

        logger.info(
            "SPECIALIST_LLM_CALL specialist=%s iteration=%d llm_call_number=%d tool_calls_so_far=%d",
            specialist, iteration, llm_call_count, tool_call_count,
        )

        # ── LLM invocation strategy ────────────────────────────────────────────
        # Iteration 1 (no tool results yet): bind tools so the LLM can request context.
        # Subsequent iterations when tool_call_count hits MAX_TOOL_CALLS-1 OR the LLM
        # has already read at least one file: switch to structured output to force
        # it to produce findings rather than another tool call.
        #
        # This handles the DeepSeek behavior where bind_tools biases the model
        # toward tool calling even after it has retrieved all necessary context.
        # Relaxed to allow multi-hop retrieval.
        force_final = tool_call_count >= (MAX_TOOL_CALLS - 1) or force_final_next

        t_llm_start = time.monotonic()

        if force_final:
            # Switch to structured output: no tools available, must produce findings
            logger.info(
                "SPECIALIST_LLM_CALL_STRUCTURED specialist=%s iteration=%d "
                "(forcing findings output after %d tool calls)",
                specialist, iteration, tool_call_count,
            )
            
            # Compress history before final verdict
            messages = relevance_aware_compaction(messages)
            
            try:
                # Build a closing human message asking for the final verdict
                closing_msg = HumanMessage(
                    content=(
                        "Based on all the context retrieved above, now provide your "
                        "final security findings as JSON. "
                        "Return ONLY the JSON object — no markdown, no preamble:\n"
                        '{"findings": [...]} or {"findings": []}'
                    )
                )
                structured_result = await invoke_structured(
                    provider, messages + [closing_msg], ReviewFindings
                )
                latency_ms = int((time.monotonic() - t_llm_start) * 1000)
                llm_latency_ms += latency_ms
                usage = structured_result.usage
                usage.reviewer = specialist
                usage_dict = usage.model_dump()
                usage_dict["iteration"] = iteration
                usage_dict["llm_call_number"] = llm_call_count
                new_usages.append(usage_dict)
                _add_event({
                    "node": specialist,
                    "event": "llm_call",
                    "details": "invoke_structured (final)",
                    "latency_ms": latency_ms,
                    "tokens": usage_dict.get("total_tokens", 0)
                })

                if structured_result.response:
                    for f in structured_result.response.findings:
                        d = f.model_dump()
                        d["reviewer"] = specialist
                        d.setdefault("source", "llm")
                        findings.append(d)

                stop_reason = "final_result"
                logger.info(
                    "SPECIALIST_FINAL_RESULT specialist=%s findings=%d "
                    "llm_call_count=%d tool_call_count=%d stop_reason=%s",
                    specialist, len(findings), llm_call_count, tool_call_count, stop_reason,
                )
                break

            except Exception as exc:
                latency_ms = int((time.monotonic() - t_llm_start) * 1000)
                logger.error(
                    "SPECIALIST_LOOP_ERROR specialist=%s iteration=%d error=%s",
                    specialist, iteration, exc,
                )
                stop_reason = "provider_error"
                new_usages.append({
                    "reviewer": specialist, "provider": provider, "model": model_name,
                    "status": "failed", "latency_ms": latency_ms, "iteration": iteration,
                })
                break
        else:
            # Iteration 1+: bind tools so the LLM can request context
            tool_llm = llm.bind_tools(MCP_TOOL_DEFINITIONS)
            
            # Compress older tool results to save tokens (Selective Context Management)
            messages = relevance_aware_compaction(messages)
            
            
            # Inject context manifest
            manifest = generate_context_manifest(evidence_store, specialist, include_content=True)
            current_messages = list(messages)
            if isinstance(current_messages[0], SystemMessage):
                current_messages[0] = SystemMessage(content=system_prompt + "\n\n" + manifest)
                
            try:
                response = await safe_ainvoke(tool_llm, current_messages)
            except Exception as exc:
                latency_ms = int((time.monotonic() - t_llm_start) * 1000)
                logger.error(
                    "SPECIALIST_LOOP_ERROR specialist=%s iteration=%d error=%s latency_ms=%d",
                    specialist, iteration, exc, latency_ms,
                )
                stop_reason = "provider_error"
                new_usages.append({
                    "reviewer": specialist, "provider": provider, "model": model_name,
                    "status": "failed", "latency_ms": latency_ms, "iteration": iteration,
                })
                break
            
            latency_ms = int((time.monotonic() - t_llm_start) * 1000)
            llm_latency_ms += latency_ms
            usage = _normalize_usage(provider, model_name, response, latency_ms)
            usage.reviewer = specialist
            usage_dict = usage.model_dump()

            usage_dict["iteration"] = iteration
            usage_dict["llm_call_number"] = llm_call_count
            breakdown = compute_token_breakdown(current_messages)
            usage_dict.update(breakdown)
            new_usages.append(usage_dict)
            
            _add_event({
                "node": specialist,
                "event": "llm_call",
                "details": "bind_tools",
                "latency_ms": latency_ms,
                "tokens": usage_dict.get("total_tokens", 0)
            })

        # ── Branch A: LLM requests tool calls ─────────────────────────────────
        tool_calls = getattr(response, "tool_calls", None) or []
        if tool_calls:
            logger.info(
                "SPECIALIST_TOOL_REQUEST specialist=%s iteration=%d tool_count=%d",
                specialist, iteration, len(tool_calls),
            )
            # Append the assistant message (with tool_calls) first
            messages.append(response)

            hit_limit = False
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id") or str(uuid4())
                key = _tool_call_key(tool_name, tool_args)

                # Duplicate detection within this reviewer's current run
                if key in executed_keys:
                    logger.warning(
                        "SPECIALIST_LOOP_STOP reason=duplicate_tool_call "
                        "specialist=%s tool=%s args=%s",
                        specialist, tool_name, tool_args,
                    )
                    duplicate_mcp_calls += 1
                    # Give it a generic failure so it knows it failed, then force finalization
                    tool_result = "ERROR: Duplicate tool call requested. You must output findings now."
                    messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call_id, name=tool_name))
                    stop_reason = "duplicate_tool_call"
                    hit_limit = True
                    break

                # Tool-call count guard
                if tool_call_count >= MAX_TOOL_CALLS:
                    logger.warning(
                        "SPECIALIST_LOOP_STOP reason=max_tool_calls specialist=%s "
                        "tool_call_count=%d",
                        specialist, tool_call_count,
                    )
                    stop_reason = "max_tool_calls"
                    hit_limit = True
                    break

                # Cache check
                global_cache_key = generate_evidence_cache_key(cache_ref, tool_name, tool_args)
                cache_hit = False
                t_tool = time.monotonic()
                
                if global_cache_key in tool_cache:
                    logger.info("MCP_TOOL_CACHE_HIT tool=%s specialist=%s", tool_name, specialist)
                    tool_result = tool_cache[global_cache_key]
                    cache_hit = True
                    mcp_calls += 1 # we still count it as a conceptual request
                    # But don't increment unique_mcp_calls
                    evidence_item = normalize_evidence(tool_name, tool_args, tool_result, specialist)
                    evidence_store.append(evidence_item)
                else:
                    # Execute the tool
                    logger.info(
                        "MCP_TOOL_EXECUTED tool=%s args=%s specialist=%s",
                        tool_name, json.dumps(tool_args, sort_keys=True), specialist,
                    )
                    try:
                        tool_result = await _execute_tool(mcp_client, tool_name, tool_args, repo_path)
                        tool_cache[global_cache_key] = tool_result
                        
                        # Normalize and store evidence
                        evidence_item = normalize_evidence(tool_name, tool_args, tool_result, specialist)
                        evidence_store.append(evidence_item)
                        
                    except Exception as tool_exc:
                        tool_result = f"ERROR: MCP tool {tool_name!r} failed: {tool_exc}"
                        logger.error("MCP tool %r failed: %s", tool_name, tool_exc)
                        
                    mcp_calls += 1
                    unique_mcp_calls += 1

                tool_duration_ms = int((time.monotonic() - t_tool) * 1000)
                mcp_latency_ms += tool_duration_ms
                
                executed_keys.add(key)
                _add_event({
                    "node": specialist,
                    "event": "tool_call",
                    "details": f"{tool_name}({json.dumps(tool_args)})",
                    "latency_ms": tool_duration_ms,
                    "tokens": 0,
                    "cache_hit": cache_hit
                })
                tool_call_count += 1
                tools_used.append(tool_name)
                if tool_name == "read_file":
                    context_files.append(tool_args.get("file_path", ""))

                # Append tool result as ToolMessage
                messages.append(
                    ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                )

                logger.info(
                    "SPECIALIST_CONTEXT_UPDATED specialist=%s file=%s "
                    "chars=%d duration_ms=%d tool_call_count=%d",
                    specialist,
                    tool_args.get("file_path", tool_name),
                    len(tool_result),
                    tool_duration_ms,
                    tool_call_count,
                )

            if hit_limit:
                force_final_next = True
                logger.info(
                    "SPECIALIST_LOOP_CONTINUE (forcing final on next iteration) specialist=%s next_iteration=%d",
                    specialist, iteration + 1,
                )
                continue

            # Continue loop — next LLM call will see the tool results
            logger.info(
                "SPECIALIST_LOOP_CONTINUE specialist=%s next_iteration=%d",
                specialist, iteration + 1,
            )
            continue

        # ── Branch B: No tool calls — extract final findings ──────────────────
        logger.info(
            "SPECIALIST_FINISHED_TOOLS specialist=%s at iteration %d — forcing final structured output",
            specialist, iteration,
        )
        messages = relevance_aware_compaction(messages)
        
        try:
            t_final = time.monotonic()
            
            # Create a compact evidence package for final extraction
            compact_manifest = generate_context_manifest(evidence_store, specialist, include_content=True)
            final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\n\n{compact_manifest}"
            closing_msg = HumanMessage(content=final_package_prompt)
            
            # Do not send the entire ReAct transcript
            final_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content),
                closing_msg
            ]
            
            structured_result = await invoke_structured(
                provider, final_messages, ReviewFindings
            )
            r_latency = int((time.monotonic() - t_final) * 1000)
            llm_latency_ms += r_latency
            
            s_usage = structured_result.usage
            s_usage.reviewer = specialist
            s_dict = s_usage.model_dump()

            s_dict["iteration"] = iteration
            s_dict["llm_call_number"] = llm_call_count + 1
            breakdown = compute_token_breakdown(final_messages)
            s_dict.update(breakdown)
            new_usages.append(s_dict)
            llm_call_count += 1
            
            _add_event({
                "node": specialist,
                "event": "llm_call",
                "details": "invoke_structured (final)",
                "latency_ms": r_latency,
                "tokens": s_dict.get("total_tokens", 0)
            })

            final_findings = []
            if structured_result.response:
                for f in structured_result.response.findings:
                    d = f.model_dump()
                    d["reviewer"] = specialist
                    d.setdefault("source", "llm")
                    final_findings.append(d)
            findings = final_findings
            stop_reason = "final_result"
        except Exception as exc:
            logger.error("Final structured extraction failed: %s", exc, exc_info=True)
            stop_reason = "provider_error"
            
        break

    # Handle max_iterations exit or timeout
    if not findings:
        if stop_reason == "unknown":
            stop_reason = "max_iterations"
        logger.warning(
            "SPECIALIST_LOOP_STOP reason=%s specialist=%s "
            "iteration=%d. Forcing final structured output.",
            stop_reason, specialist, iteration,
        )
        
        messages = relevance_aware_compaction(messages)
        
        try:
            fallback_count += 1
            t_llm_start = time.monotonic()
            
            compact_manifest = generate_context_manifest(evidence_store, specialist, include_content=True)
            final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\n\n{compact_manifest}"
            
            final_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content),
                HumanMessage(content=final_package_prompt)
            ]
            
            repair_result = await invoke_structured(provider, final_messages, ReviewFindings)
            latency_ms = int((time.monotonic() - t_llm_start) * 1000)
            llm_latency_ms += latency_ms
            
            _add_event({
                "node": specialist,
                "event": "llm_call",
                "details": "invoke_structured (fallback)",
                "latency_ms": latency_ms,
                "tokens": repair_result.usage.total_tokens if repair_result.usage else 0
            })
            
            if repair_result.response:
                for f in repair_result.response.findings:
                    d = f.model_dump()
                    d["reviewer"] = specialist
                    d.setdefault("source", "llm")
                    findings.append(d)
        except Exception as repair_exc:
            logger.error("Final fallback structured call failed: %s", repair_exc, exc_info=True)

    total_latency_ms = int((time.monotonic() - review_start) * 1000)

    loop_summary = {
        "specialist_name": specialist,
        "llm_call_count": llm_call_count,
        "tool_call_count": tool_call_count,
        "iteration_count": iteration,
        "tools_used": tools_used,
        "context_files_retrieved": context_files,
        "stop_reason": stop_reason,
        "total_latency_ms": total_latency_ms,
        "finding_count": len(findings),
    }
    logger.info(
        "SPECIALIST_LOOP_SUMMARY specialist=%s llm_calls=%d tool_calls=%d "
        "iterations=%d stop_reason=%s findings=%d latency_ms=%d",
        specialist, llm_call_count, tool_call_count, iteration,
        stop_reason, len(findings), total_latency_ms,
    )

    # Build result dict — only write the KEYS this node owns
    existing_latencies = dict(state.get("reviewer_latencies", {}))
    existing_latencies[f"{specialist}_ms"] = total_latency_ms
    # Store loop summary in reviewer_latencies (merge reducer — safe from parallel)
    existing_latencies[f"{specialist}_loop"] = loop_summary

    result: dict = {
        f"{specialist}_raw_findings": findings,
        "llm_usages": new_usages,
        "reviewer_latencies": existing_latencies,
        "timeline": new_timeline,
        
        # New metrics additions
        "mcp_calls": mcp_calls,
        "unique_mcp_calls": unique_mcp_calls,
        "duplicate_mcp_calls": duplicate_mcp_calls,
        "agent_iterations": iteration,
        "retry_count": retry_count,
        "fallback_count": fallback_count,
        "timeout_count": timeout_count,
        "llm_latency_ms": llm_latency_ms,
        "mcp_latency_ms": mcp_latency_ms,
        "tool_cache": tool_cache,
        "evidence_store": evidence_store,
    }

    # Write errors only if there are any (use the right key per specialist)
    # Note: do not include pre-existing errors from state — the append reducer handles that
    return result
