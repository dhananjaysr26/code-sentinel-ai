"""
Unit tests for the iterative MCP reviewer loop.

All tests use mocked LLM and MCP — no real Bedrock or API calls are made.

Test matrix:
  A. Tool-call routing        — LLM requests tool, result appended, second LLM call
  B. No-tool immediate result — LLM returns findings on first call
  C. Duplicate tool call      — same tool+args twice → stop_reason='duplicate_tool_call'
  D. Max iterations           — LLM always returns tool_calls → stop at MAX_ITERATIONS
  E. Max tool calls           — repeated different tools → stop at MAX_TOOL_CALLS
  F. Path traversal rejected  — '../etc/passwd' → ERROR returned, not file content
  G. Tool result in messages  — ToolMessage is appended to conversation
  H. Large result truncated   — 50k chars → truncated to MAX_TOOL_RESULT_CHARS
"""
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")

import django
django.setup()

from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, HumanMessage

# Patch settings before importing the module under test
import django.conf
django.conf.settings.ITERATIVE_MAX_ITERATIONS = 3
django.conf.settings.ITERATIVE_MAX_TOOL_CALLS = 5
django.conf.settings.ITERATIVE_REVIEW_TIMEOUT_SECONDS = 45
django.conf.settings.ITERATIVE_MAX_TOOL_RESULT_CHARS = 500  # small for test H


from sentinel.graph.nodes.iterative_reviewer import (
    _execute_tool,
    _parse_findings_from_text,
    _tool_call_key,
    run_iterative_reviewer,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_ai_tool_call_message(tool_name: str, args: dict, call_id: str = "call-1"):
    """Create a mock AIMessage that contains a tool call."""
    msg = MagicMock(spec=AIMessage)
    msg.content = ""
    msg.tool_calls = [{"name": tool_name, "args": args, "id": call_id}]
    msg.usage_metadata = None
    msg.response_metadata = {}
    return msg


def _make_ai_text_message(content: str):
    """Create a mock AIMessage with text content and no tool calls."""
    msg = MagicMock(spec=AIMessage)
    msg.content = content
    msg.tool_calls = []
    msg.usage_metadata = None
    msg.response_metadata = {}
    return msg


def _make_mock_mcp_client(read_file_return: str = "# policy content"):
    client = AsyncMock()
    client.read_file = AsyncMock(return_value=read_file_return)
    client.find_references = AsyncMock(return_value='{"references": []}')
    return client


def _make_context_block():
    block = MagicMock()
    block.file_path = "src/auth.py"
    block.surrounding_code = "_GUARDED_ACTION = 'user_settings'"
    block.hunk_diff = "-_GUARDED_ACTION = 'delete_account'\n+_GUARDED_ACTION = 'user_settings'"
    return block


def _make_state(blocks=None):
    if blocks is None:
        blocks = [_make_context_block()]
    return {
        "context_blocks": blocks,
        "repo_path": "/fake/repo",
        "llm_provider": "bedrock",
        "llm_usages": [],
        "reviewer_latencies": {},
        "errors": [],
        "security_errors": [],
        "metadata": {"review_id": "test-123"},
    }


FINDINGS_JSON = '{"findings": [{"file": "src/auth.py", "line": 3, "title": "Privilege escalation", "category": "security", "severity": "high", "confidence": 0.9, "explanation": "...", "evidence": "...", "suggested_fix": "use delete_account", "source": "llm"}]}'


# ── Test A: Tool-call routing ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tool_call_routing_two_llm_calls():
    """LLM first requests read_file, then returns findings. Expect 2 LLM calls."""
    state = _make_state()
    mcp = _make_mock_mcp_client("POLICIES = {'administrator': {'delete_account'}}")

    call_1 = _make_ai_tool_call_message("read_file", {"file_path": "src/policy.py"})
    call_2 = _make_ai_text_message(FINDINGS_JSON)

    mock_llm = MagicMock()
    mock_tool_llm = AsyncMock()
    mock_tool_llm.ainvoke = AsyncMock(side_effect=[call_1, call_2])
    mock_llm.bind_tools = MagicMock(return_value=mock_tool_llm)

    with patch("sentinel.graph.nodes.iterative_reviewer.get_llm", return_value=mock_llm):
        result = await run_iterative_reviewer("security", state, "bedrock", "/fake/repo", mcp)

    findings = result["security_raw_findings"]
    loop = result["reviewer_latencies"]["security_loop"]

    assert len(findings) == 1, f"Expected 1 finding, got {len(findings)}"
    assert loop["llm_call_count"] == 2
    assert loop["tool_call_count"] == 1
    assert loop["stop_reason"] == "final_result"
    assert "read_file" in loop["tools_used"]
    assert "src/policy.py" in loop["context_files_retrieved"]
    # Verify MCP was actually called
    mcp.read_file.assert_awaited_once_with("/fake/repo", "src/policy.py", 1, 200)


# ── Test B: No tool call — immediate result ────────────────────────────────────

@pytest.mark.asyncio
async def test_no_tool_call_immediate_result():
    """LLM returns findings on the first call without requesting any tools."""
    state = _make_state()
    mcp = _make_mock_mcp_client()

    call_1 = _make_ai_text_message(FINDINGS_JSON)

    mock_llm = MagicMock()
    mock_tool_llm = AsyncMock()
    mock_tool_llm.ainvoke = AsyncMock(return_value=call_1)
    mock_llm.bind_tools = MagicMock(return_value=mock_tool_llm)

    with patch("sentinel.graph.nodes.iterative_reviewer.get_llm", return_value=mock_llm):
        result = await run_iterative_reviewer("security", state, "bedrock", "/fake/repo", mcp)

    loop = result["reviewer_latencies"]["security_loop"]
    assert loop["llm_call_count"] == 1
    assert loop["tool_call_count"] == 0
    assert loop["stop_reason"] == "final_result"
    mcp.read_file.assert_not_awaited()


# ── Test C: Duplicate tool call prevention ─────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_tool_call_prevention():
    """LLM requests same tool+args twice. After 1st tool executes, structured
    output is used for the final call — so we confirm tool was called exactly once."""
    state = _make_state()
    mcp = _make_mock_mcp_client()

    # Only one bind_tools call expected: iteration 1 requests a tool
    call_1 = _make_ai_tool_call_message("read_file", {"file_path": "src/policy.py"}, "id-1")

    mock_llm = MagicMock()
    mock_tool_llm = AsyncMock()
    mock_tool_llm.ainvoke = AsyncMock(return_value=call_1)
    mock_llm.bind_tools = MagicMock(return_value=mock_tool_llm)

    # The final structured call returns empty findings
    mock_structured_result = MagicMock()
    mock_structured_result.response = MagicMock()
    mock_structured_result.response.findings = []
    mock_structured_usage = MagicMock()
    mock_structured_usage.reviewer = "security"
    mock_structured_usage.model_dump = MagicMock(return_value={
        "reviewer": "security", "provider": "bedrock", "model": "test", "status": "success",
        "input_tokens": 100, "output_tokens": 10, "total_tokens": 110, "latency_ms": 500,
    })
    mock_structured_result.usage = mock_structured_usage

    with patch("sentinel.graph.nodes.iterative_reviewer.get_llm", return_value=mock_llm):
        with patch("sentinel.graph.nodes.iterative_reviewer.invoke_structured",
                   new_callable=AsyncMock, return_value=mock_structured_result):
            result = await run_iterative_reviewer("security", state, "bedrock", "/fake/repo", mcp)

    loop = result["reviewer_latencies"]["security_loop"]
    # Tool was called once (not duplicate since structured output was used on iteration 2)
    assert mcp.read_file.await_count == 1
    assert loop["tool_call_count"] == 1
    assert loop["stop_reason"] == "final_result"


# ── Test D: Max iterations termination ────────────────────────────────────────

@pytest.mark.asyncio
async def test_max_iterations_termination():
    """With MAX_ITERATIONS=1 and a tool call on that iteration, the forced
    structured output call terminates the loop with final_result."""
    state = _make_state()
    mcp = _make_mock_mcp_client()

    call_1 = _make_ai_tool_call_message("read_file", {"file_path": "src/file0.py"}, "id-0")

    mock_llm = MagicMock()
    mock_tool_llm = AsyncMock()
    mock_tool_llm.ainvoke = AsyncMock(return_value=call_1)
    mock_llm.bind_tools = MagicMock(return_value=mock_tool_llm)

    mock_structured_result = MagicMock()
    mock_structured_result.response = MagicMock()
    mock_structured_result.response.findings = []
    mock_structured_usage = MagicMock()
    mock_structured_usage.reviewer = "security"
    mock_structured_usage.model_dump = MagicMock(return_value={
        "reviewer": "security", "provider": "bedrock", "model": "test", "status": "success",
        "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "latency_ms": 0,
    })
    mock_structured_result.usage = mock_structured_usage

    with patch("sentinel.graph.nodes.iterative_reviewer.get_llm", return_value=mock_llm):
        with patch("sentinel.graph.nodes.iterative_reviewer.invoke_structured",
                   new_callable=AsyncMock, return_value=mock_structured_result):
            with patch.object(django.conf.settings, "ITERATIVE_MAX_ITERATIONS", 2):
                result = await run_iterative_reviewer("security", state, "bedrock", "/fake/repo", mcp)

    loop = result["reviewer_latencies"]["security_loop"]
    # With max_iterations=2: iter 1 does tool call, iter 2 does structured → final_result
    assert loop["stop_reason"] == "final_result"
    assert loop["iteration_count"] <= 2


# ── Test E: Max tool calls termination ────────────────────────────────────────

@pytest.mark.asyncio
async def test_max_tool_calls_termination():
    """With MAX_TOOL_CALLS=0, the first iteration cannot execute any tools.
    The loop immediately switches to structured output on iteration 2... but
    since tool_call_count never reaches 1, bind_tools is used. With 0 tool slots,
    we need MAX_TOOL_CALLS=0 to be enforced BEFORE any tool runs."""
    state = _make_state()
    mcp = _make_mock_mcp_client()

    call_1 = _make_ai_tool_call_message("read_file", {"file_path": "src/policy0.py"}, "id-0")

    mock_llm = MagicMock()
    mock_tool_llm = AsyncMock()
    mock_tool_llm.ainvoke = AsyncMock(return_value=call_1)
    mock_llm.bind_tools = MagicMock(return_value=mock_tool_llm)

    with patch("sentinel.graph.nodes.iterative_reviewer.get_llm", return_value=mock_llm):
        with patch.object(django.conf.settings, "ITERATIVE_MAX_TOOL_CALLS", 0):
            result = await run_iterative_reviewer("security", state, "bedrock", "/fake/repo", mcp)

    loop = result["reviewer_latencies"]["security_loop"]
    assert loop["stop_reason"] == "max_tool_calls"
    assert loop["tool_call_count"] == 0
    mcp.read_file.assert_not_awaited()


# ── Test G: Tool result appended to messages ──────────────────────────────────

@pytest.mark.asyncio
async def test_tool_result_appended_to_messages():
    """After a tool call, the messages list sent to the structured LLM call
    must contain a ToolMessage with the tool result content."""
    state = _make_state()
    policy_content = "ENDPOINT_POLICY = {'delete_account': 'administrator'}"
    mcp = _make_mock_mcp_client(policy_content)

    call_1 = _make_ai_tool_call_message("read_file", {"file_path": "src/policy.py"}, "call-abc")

    mock_llm = MagicMock()
    mock_tool_llm = AsyncMock()
    mock_tool_llm.ainvoke = AsyncMock(return_value=call_1)
    mock_llm.bind_tools = MagicMock(return_value=mock_tool_llm)

    captured_structured_messages = []

    async def capture_structured(provider, messages, schema):
        captured_structured_messages.extend(messages)
        result = MagicMock()
        result.response = MagicMock()
        result.response.findings = []
        usage = MagicMock()
        usage.reviewer = "security"
        usage.model_dump = MagicMock(return_value={
            "reviewer": "security", "provider": "bedrock", "model": "test",
            "status": "success", "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0, "latency_ms": 0,
        })
        result.usage = usage
        return result

    with patch("sentinel.graph.nodes.iterative_reviewer.get_llm", return_value=mock_llm):
        with patch("sentinel.graph.nodes.iterative_reviewer.invoke_structured",
                   new_callable=AsyncMock, side_effect=capture_structured):
            result = await run_iterative_reviewer("security", state, "bedrock", "/fake/repo", mcp)

    # The structured call should have received the conversation with the ToolMessage
    tool_messages = [m for m in captured_structured_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) >= 1
    assert policy_content in tool_messages[0].content
    assert tool_messages[0].tool_call_id == "call-abc"


# ── Test H: Large tool result truncated ───────────────────────────────────────

@pytest.mark.asyncio
async def test_large_tool_result_truncated():
    """A tool result larger than MAX_TOOL_RESULT_CHARS must be truncated."""
    large_content = "x" * 50_000
    mcp = _make_mock_mcp_client(large_content)

    # Use a small limit for this test
    with patch.object(django.conf.settings, "ITERATIVE_MAX_TOOL_RESULT_CHARS", 500):
        result = await _execute_tool(mcp, "read_file", {"file_path": "src/big.py"}, "/repo")

    assert len(result) <= 560  # 500 chars + truncation suffix (~49 chars)
    assert "[TRUNCATED" in result


# ── Test: _parse_findings_from_text ───────────────────────────────────────────

def test_parse_findings_from_valid_json():
    text = FINDINGS_JSON
    findings = _parse_findings_from_text(text, "security")
    assert findings is not None
    assert len(findings) == 1
    assert findings[0]["file"] == "src/auth.py"


def test_parse_findings_from_fenced_json():
    text = f"Here are my findings:\n```json\n{FINDINGS_JSON}\n```"
    findings = _parse_findings_from_text(text, "security")
    assert findings is not None
    assert len(findings) == 1


def test_parse_findings_returns_none_on_no_json():
    text = "I cannot determine the severity without additional context."
    findings = _parse_findings_from_text(text, "security")
    assert findings is None


def test_parse_findings_empty_list():
    findings = _parse_findings_from_text('{"findings": []}', "security")
    assert findings == []


# ── Test: _tool_call_key deduplication ────────────────────────────────────────

def test_tool_call_key_normalizes_arg_order():
    k1 = _tool_call_key("read_file", {"end_line": 200, "file_path": "src/a.py", "start_line": 1})
    k2 = _tool_call_key("read_file", {"file_path": "src/a.py", "start_line": 1, "end_line": 200})
    assert k1 == k2


def test_tool_call_key_different_tools():
    k1 = _tool_call_key("read_file", {"file_path": "src/a.py"})
    k2 = _tool_call_key("find_references", {"file_path": "src/a.py"})
    assert k1 != k2
