import pytest
from sentinel.graph.context_engineering import (
    normalize_evidence,
    generate_context_manifest,
    relevance_aware_compaction,
    generate_evidence_cache_key,
    EvidenceItem
)
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

def test_evidence_normalization():
    ev = normalize_evidence("read_file", {"file_path": "src/api.py", "start_line": 10, "end_line": 20}, "print('hello')", "correctness")
    assert ev.path == "src/api.py"
    assert ev.line_start == 10
    assert ev.line_end == 20
    assert ev.evidence_type == "code_snippet"
    assert ev.content == "print('hello')"

def test_context_manifest():
    ev = EvidenceItem(reviewer="security", source="read_file", path="src/api.py", line_start=1, line_end=5, evidence_type="code_snippet", summary="Read src/api.py", content="import os")
    manifest = generate_context_manifest([ev])
    assert "src/api.py (lines 1-5)" in manifest
    assert "Read src/api.py" in manifest

def test_relevance_aware_compaction():
    messages = [

        SystemMessage(content="Sys"),
        HumanMessage(content="Task"),
        AIMessage(content="Need file 0"),
        ToolMessage(content="large string" * 100, tool_call_id="0", name="read_file"),
        AIMessage(content="Need file 1"),
        ToolMessage(content="large string" * 100, tool_call_id="1", name="read_file"),
        AIMessage(content="Need another"),
        ToolMessage(content="recent string", tool_call_id="2", name="read_file"),

    ]
    compacted = relevance_aware_compaction(messages)
    assert len(compacted) == 8
    assert "CONTENT COMPACTED" in compacted[3].content
    assert compacted[-1].content == "recent string"

def test_cache_key():
    key1 = generate_evidence_cache_key("commit1", "read_file", {"file_path": "a.py"})
    key2 = generate_evidence_cache_key("commit2", "read_file", {"file_path": "a.py"})
    assert key1 != key2
