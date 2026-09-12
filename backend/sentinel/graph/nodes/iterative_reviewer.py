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

from sentinel.schemas.findings import ReviewFindings
from sentinel.services.llm_service import invoke_structured, get_llm, _normalize_usage

logger = logging.getLogger(__name__)


# ── MCP Tool definitions sent to the LLM via bind_tools() ─────────────────────
MCP_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the repository to understand code context, "
                "type definitions, policy mappings, or configuration values. "
                "Use this when a changed constant, identifier, or function call "
                "refers to something defined in a file not already in the context."
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
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_references",
            "description": (
                "Find all usages/references of a symbol (function, class, variable) "
                "across the repository. Use to understand callers or consumers of a "
                "changed function."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Name of the symbol to search for, e.g. '_GUARDED_ACTION'",
                    }
                },
                "required": ["symbol"],
            },
        },
    },
]

# ── Specialist system prompts ──────────────────────────────────────────────────
_SECURITY_SYSTEM_PROMPT = """\
You are a senior security code reviewer with access to MCP tools for retrieving \
repository context.

You are reviewing a code diff. The initial context is INTENTIONALLY LIMITED — it \
contains only the changed file and immediate surrounding code. This is by design.

WORKFLOW:
1. Review the diff and current context.
2. If you need to understand what a changed constant, key, or identifier means, \
call read_file ONCE to read the relevant file.
3. After receiving the file contents, immediately analyze the evidence and return \
your findings in JSON. Do NOT call any tool again after you have received the file.
4. If you have no additional questions after the initial context, return findings directly.

CRITICAL RULES:
- NEVER call the same tool with the same arguments more than once. If you already \
received the content of a file, do NOT request it again.
- Once you have read the policy/config file that defines a changed identifier, \
IMMEDIATELY produce your findings — do not request more files unless strictly necessary.
- Do NOT guess about the privilege level of opaque strings. Use read_file first.
- Return a finding ONLY when supported by evidence from code you have actually read.
- If context is still insufficient after tool calls, return {"findings": []}.
- Only report genuine security vulnerabilities. Do NOT report general correctness bugs, logic errors, or style issues — those are handled by a separate reviewer.

AUTHORIZATION REVIEW FOCUS:
When an authorization-related constant, action key, role, or policy identifier \
changes and its definition is not visible in the diff, call read_file on the file \
that defines it. Then compare the old value's privilege level to the new value's \
privilege level. If the new value grants lower privilege than the old, report a \
privilege escalation vulnerability.

OUTPUT FORMAT (return ONLY this JSON, no markdown, no extra text):
{"findings": [{"file": "src/auth.py", "line": 3, "title": "...", \
"category": "security", "severity": "high", "confidence": 0.9, \
"explanation": "...", "evidence": "...", "suggested_fix": "...", "source": "llm"}]}

If no security vulnerability exists, return exactly: {"findings": []}"""

_CORRECTNESS_SYSTEM_PROMPT = """\
You are a senior correctness code reviewer with access to MCP tools for retrieving \
repository context.

You are reviewing a code diff. The initial context is INTENTIONALLY LIMITED — it \
contains only the changed file and immediate surrounding code.

CRITICAL INSTRUCTIONS:
- Review EVERY changed file, EVERY changed function, and EVERY changed hunk.
- Continue looking after finding one issue. Do NOT stop after the first finding.
- Return ALL independent findings across all files in the diff.
- If the behavior of changed code depends on a callee, type definition, invariant, \
or external contract NOT provided in the current context, use MCP tools to retrieve it.
- Use read_file to inspect relevant definitions. Use find_references to inspect callers.
- Return a finding ONLY when supported by evidence from code you have actually read.
- Only report genuine correctness bugs, NOT style issues.
- Do NOT report security vulnerabilities (e.g. SQL injection, hardcoded secrets) — those are handled by a separate reviewer.

SYSTEMATIC CHECKLIST (Check for these specific classes of correctness bugs):
1. Off-by-one errors and loop boundary conditions
2. Null/None dereferences and missing existence checks
3. Missing dictionary keys or out-of-bounds indexing
4. Float equality and numeric precision correctness
5. Resource leaks (unclosed files, network connections, etc.)
6. Exception-path cleanup and swallowed exceptions
7. Broken invariants or incorrect state transitions
8. Incorrect return values or mismatched API contracts
9. Incorrect boolean conditions or inverted logic
10. Race conditions or thread-safety issues

AFTER gathering all necessary context and checking ALL hunks against the checklist, \
return your final findings as JSON:

{"findings": [{"file": "src/auth.py", "line": 3, "title": "...", \
"category": "correctness", "severity": "high", "confidence": 0.9, \
"explanation": "...", "evidence": "...", "suggested_fix": "...", "source": "llm"}]}

If no correctness bug exists across all files, return: {"findings": []}"""


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
        findings = data.get("findings", [])
        for f in findings:
            f.setdefault("reviewer", specialist)
            f.setdefault("source", "llm")
        return findings
    except (json.JSONDecodeError, AttributeError):
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
    MAX_ITERATIONS = getattr(settings, "ITERATIVE_MAX_ITERATIONS", 5)
    MAX_TOOL_CALLS = getattr(settings, "ITERATIVE_MAX_TOOL_CALLS", 5)
    MAX_TIMEOUT = getattr(settings, "ITERATIVE_REVIEW_TIMEOUT_SECONDS", 45)

    review_start = time.monotonic()
    executed_keys: set[str] = set()
    iteration = 0
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

    logger.info(
        "REVIEW_LOOP_START specialist=%s review_id=%s context_blocks=%d",
        specialist, review_id, len(blocks),
    )

    # Build initial messages
    system_prompt = (
        _SECURITY_SYSTEM_PROMPT if specialist == "security" else _CORRECTNESS_SYSTEM_PROMPT
    )
    human_content = "Please review the following code changes:\n\n"
    for block in blocks:
        human_content += f"File: {block.file_path}\n"
        human_content += f"```python\n{block.surrounding_code}\n```\n"
        human_content += f"Diff:\n```diff\n{block.hunk_diff}\n```\n\n"

    messages: list = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]

    llm = get_llm(provider)
    model_name = _get_model_name(llm)

    # ── Main loop ──────────────────────────────────────────────────────────────
    new_timeline = []
    while iteration < MAX_ITERATIONS:
        # Timeout guard
        elapsed = time.monotonic() - review_start
        if elapsed > MAX_TIMEOUT:
            stop_reason = "timeout"
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
                usage = structured_result.usage
                usage.reviewer = specialist
                usage_dict = usage.model_dump()
                usage_dict["iteration"] = iteration
                usage_dict["llm_call_number"] = llm_call_count
                new_usages.append(usage_dict)
                new_timeline.append({
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
            # Iteration 1: bind tools so the LLM can request context
            tool_llm = llm.bind_tools(MCP_TOOL_DEFINITIONS)
            try:
                response = await tool_llm.ainvoke(messages)
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
            usage = _normalize_usage(provider, model_name, response, latency_ms)
            usage.reviewer = specialist
            usage_dict = usage.model_dump()
            usage_dict["iteration"] = iteration
            usage_dict["llm_call_number"] = llm_call_count
            new_usages.append(usage_dict)
            
            new_timeline.append({
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

                # Duplicate detection
                if key in executed_keys:
                    logger.warning(
                        "SPECIALIST_LOOP_STOP reason=duplicate_tool_call "
                        "specialist=%s tool=%s args=%s",
                        specialist, tool_name, tool_args,
                    )
                    # Return the cached result once so the LLM has it, then stop
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

                # Execute the tool
                t_tool = time.monotonic()
                logger.info(
                    "MCP_TOOL_EXECUTED tool=%s args=%s specialist=%s",
                    tool_name, json.dumps(tool_args, sort_keys=True), specialist,
                )
                try:
                    tool_result = await _execute_tool(mcp_client, tool_name, tool_args, repo_path)
                except Exception as tool_exc:
                    tool_result = f"ERROR: MCP tool {tool_name!r} failed: {tool_exc}"
                    logger.error("MCP tool %r failed: %s", tool_name, tool_exc)

                tool_duration_ms = int((time.monotonic() - t_tool) * 1000)
                executed_keys.add(key)
                new_timeline.append({
                    "node": specialist,
                    "event": "tool_call",
                    "details": f"{tool_name}({json.dumps(tool_args)})",
                    "latency_ms": tool_duration_ms,
                    "tokens": 0
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
        text = getattr(response, "content", "") or ""
        parsed = _parse_findings_from_text(text, specialist)

        if parsed is None:
            # JSON not found in text — try one structured-output repair call
            logger.warning(
                "JSON parse failed for %s at iteration %d — attempting repair call",
                specialist, iteration,
            )
            try:
                repair_result = await invoke_structured(
                    provider, messages + [response], ReviewFindings
                )
                repair_usage = repair_result.usage
                repair_usage.reviewer = specialist
                repair_usage_dict = repair_usage.model_dump()
                repair_usage_dict["iteration"] = iteration
                repair_usage_dict["llm_call_number"] = llm_call_count + 1
                new_usages.append(repair_usage_dict)
                llm_call_count += 1
                
                new_timeline.append({
                    "node": specialist,
                    "event": "llm_call",
                    "details": "invoke_structured (repair)",
                    "latency_ms": 0,  # approximate or can't easily measure here without t_repair
                    "tokens": repair_usage_dict.get("total_tokens", 0)
                })

                repaired_findings = []
                if repair_result.response:
                    for f in repair_result.response.findings:
                        d = f.model_dump()
                        d["reviewer"] = specialist
                        repaired_findings.append(d)
                findings = repaired_findings
                logger.info(
                    "REPAIR_CALL_SUCCESS specialist=%s findings=%d",
                    specialist, len(findings),
                )
            except Exception as repair_exc:
                logger.error(
                    "REPAIR_CALL_FAILED specialist=%s error=%s",
                    specialist, repair_exc,
                )
                findings = []
        else:
            findings = parsed

        stop_reason = "final_result"
        logger.info(
            "SPECIALIST_FINAL_RESULT specialist=%s findings=%d "
            "llm_call_count=%d tool_call_count=%d stop_reason=%s",
            specialist, len(findings), llm_call_count, tool_call_count, stop_reason,
        )
        break

    # Handle max_iterations exit or timeout
    if stop_reason in ("unknown", "max_iterations", "timeout") and not findings:
        if stop_reason == "unknown":
            stop_reason = "max_iterations"
        logger.warning(
            "SPECIALIST_LOOP_STOP reason=%s specialist=%s "
            "iteration=%d. Forcing final structured output.",
            stop_reason, specialist, iteration,
        )
        try:
            closing_msg = HumanMessage(
                content="Based on all the context retrieved above, now provide your final findings as JSON. Return ONLY the JSON object."
            )
            repair_result = await invoke_structured(provider, messages + [closing_msg], ReviewFindings)
            
            new_timeline.append({
                "node": specialist,
                "event": "llm_call",
                "details": "invoke_structured (fallback)",
                "latency_ms": 0,
                "tokens": repair_result.usage.total_tokens if repair_result.usage else 0
            })
            
            if repair_result.response:
                for f in repair_result.response.findings:
                    d = f.model_dump()
                    d["reviewer"] = specialist
                    d.setdefault("source", "llm")
                    findings.append(d)
        except Exception as repair_exc:
            logger.error("Final fallback structured call failed: %s", repair_exc)

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
    }

    # Write errors only if there are any (use the right key per specialist)
    # Note: do not include pre-existing errors from state — the append reducer handles that
    return result
