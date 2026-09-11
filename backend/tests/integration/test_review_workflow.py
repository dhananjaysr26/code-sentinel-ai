"""
Integration test: verifies the review workflow runs end-to-end with a mocked LLM.

Tests:
  - parse_diff node processes a real git diff
  - build_context node calls MCP client (mocked)
  - correctness_review node calls LLM (mocked)
  - validate_findings node validates schema
  - Full workflow produces Finding objects
"""
import os
import asyncio
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from unittest.mock import AsyncMock, MagicMock, patch
from sentinel.schemas.findings import Finding, Severity, Category, Source, ReviewFindings
from sentinel.schemas.context import ContextBlock


@pytest.mark.asyncio
async def test_parse_diff_node_with_real_repo(temp_git_repo):
    """parse_diff node reads a real git repo and produces DiffHunk objects."""
    import django
    django.setup()

    from sentinel.graph.nodes.diff_parser_node import parse_diff_node

    state = {
        "repo_path": str(temp_git_repo),
        "base_ref": "HEAD~1",
        "target_ref": "HEAD",
        "errors": [],
        "metadata": {"review_id": "test-123", "node_durations": {}},
    }

    result = await parse_diff_node(state)

    assert result["raw_diff"] != ""
    assert len(result["changed_files"]) > 0
    assert len(result["diff_hunks"]) > 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_validate_findings_node_valid_input():
    """validate_findings filters valid findings and drops invalid ones."""
    import django
    django.setup()

    from sentinel.graph.nodes.validate_findings_node import validate_findings_node

    valid_raw = {
        "id": "test-id-1",
        "file": "src/user.py",
        "line": 42,
        "title": "NoneType dereference",
        "category": "correctness",
        "severity": "HIGH",
        "confidence": 0.9,
        "explanation": "user.profile is not checked",
        "evidence": "user.profile.email",
        "suggested_fix": None,
        "source": "llm",
    }
    invalid_raw = {"garbage": "data"}

    state = {
        "raw_findings": [valid_raw, invalid_raw],
        "errors": [],
        "metadata": {"review_id": "test", "node_durations": {}},
    }

    result = await validate_findings_node(state)

    assert len(result["findings"]) == 1
    assert isinstance(result["findings"][0], Finding)
    assert len(result["errors"]) == 1  # invalid_raw caused one error


@pytest.mark.asyncio
async def test_full_workflow_with_mocked_llm(temp_git_repo):
    """Full graph runs end-to-end with mocked LLM and MCP client."""
    import django
    django.setup()

    mock_finding = Finding(
        file="app.py",
        line=1,
        title="Test finding",
        category=Category.CORRECTNESS,
        severity=Severity.HIGH,
        confidence=0.9,
        explanation="test explanation",
        evidence="def hello():",
        source=Source.LLM,
    )
    mock_review_findings = ReviewFindings(findings=[mock_finding])

    # Mock the LLM call in correctness_review_node
    mock_structured_llm = AsyncMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_review_findings)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

    # Mock MCP client to avoid requiring a running MCP server
    mock_mcp_read = AsyncMock(return_value="1: def hello():\n2:     pass\n")

    with (
        patch("sentinel.graph.nodes.correctness_reviewer_node.ChatOpenAI", return_value=mock_llm),
        patch("sentinel.graph.nodes.context_builder_node.StdioMCPClient") as MockMCP,
    ):
        mock_mcp_instance = AsyncMock()
        mock_mcp_instance.read_file = mock_mcp_read
        MockMCP.return_value = mock_mcp_instance

        from sentinel.graph.workflow import build_review_graph
        graph = build_review_graph()

        initial_state = {
            "repo_path": str(temp_git_repo),
            "base_ref": "HEAD~1",
            "target_ref": "HEAD",
            "raw_diff": "",
            "changed_files": [],
            "diff_hunks": [],
            "context_blocks": [],
            "raw_findings": [],
            "findings": [],
            "errors": [],
            "metadata": {"review_id": "integration-test", "node_durations": {}},
        }

        final_state = await graph.ainvoke(initial_state)

    assert len(final_state["findings"]) == 1
    assert final_state["findings"][0].title == "Test finding"
    assert final_state["errors"] == []
