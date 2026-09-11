"""Unit tests for the Finding Pydantic schema."""
import pytest
from pydantic import ValidationError

from sentinel.schemas.findings import Finding, Severity, Category, Source, ReviewFindings


VALID_FINDING = {
    "file": "src/user.py",
    "line": 42,
    "title": "NoneType dereference",
    "category": "correctness",
    "severity": "HIGH",
    "confidence": 0.95,
    "explanation": "user.profile is accessed without None check",
    "evidence": "return user.profile.email",
    "suggested_fix": "Check if user.profile is not None first",
    "source": "llm",
}


def test_valid_finding_passes():
    f = Finding(**VALID_FINDING)
    assert f.file == "src/user.py"
    assert f.severity == Severity.HIGH
    assert f.category == Category.CORRECTNESS
    assert f.source == Source.LLM
    assert f.confidence == 0.95


def test_id_auto_generated():
    f = Finding(**VALID_FINDING)
    assert f.id is not None
    assert len(f.id) > 0


def test_confidence_rounded():
    data = {**VALID_FINDING, "confidence": 0.9999}
    f = Finding(**data)
    assert f.confidence == 1.0


def test_confidence_below_zero_fails():
    data = {**VALID_FINDING, "confidence": -0.1}
    with pytest.raises(ValidationError):
        Finding(**data)


def test_confidence_above_one_fails():
    data = {**VALID_FINDING, "confidence": 1.1}
    with pytest.raises(ValidationError):
        Finding(**data)


def test_invalid_severity_fails():
    data = {**VALID_FINDING, "severity": "CATASTROPHIC"}
    with pytest.raises(ValidationError):
        Finding(**data)


def test_invalid_category_fails():
    data = {**VALID_FINDING, "category": "performance"}
    with pytest.raises(ValidationError):
        Finding(**data)


def test_missing_required_field_fails():
    data = {k: v for k, v in VALID_FINDING.items() if k != "title"}
    with pytest.raises(ValidationError):
        Finding(**data)


def test_line_can_be_none():
    data = {**VALID_FINDING, "line": None}
    f = Finding(**data)
    assert f.line is None


def test_suggested_fix_optional():
    data = {k: v for k, v in VALID_FINDING.items() if k != "suggested_fix"}
    f = Finding(**data)
    assert f.suggested_fix is None


def test_file_path_normalized():
    data = {**VALID_FINDING, "file": "./src/user.py"}
    f = Finding(**data)
    assert not f.file.startswith("./")


def test_review_findings_empty_list():
    rf = ReviewFindings()
    assert rf.findings == []


def test_review_findings_with_findings():
    rf = ReviewFindings(findings=[Finding(**VALID_FINDING)])
    assert len(rf.findings) == 1
