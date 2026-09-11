import sys
import os
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / "mcp_server"))

import json
from server import find_references, run_linter

import pytest
import shutil
import subprocess

@pytest.fixture(scope="session")
def repo_fixture(tmp_path_factory):
    repo_path = tmp_path_factory.mktemp("test_repo")
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    
    # Write Python files
    (repo_path / "main.py").write_text("""
from utils import MyClass, process_data

def main():
    obj = MyClass()
    process_data(obj)

if __name__ == '__main__':
    main()
""")

    (repo_path / "utils.py").write_text("""
class MyClass:
    def method(self):
        pass

def process_data(item):
    unused_var = 1
    item.method()
""")

    (repo_path / "non_python.txt").write_text("process_data")

    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_path, check=True)
    
    return str(repo_path)

def test_find_references_function(repo_fixture):
    # 1. function reference
    # 2. multiple references
    # 4. imported symbol
    result = json.loads(find_references(repo_fixture, "process_data"))
    assert "error" not in result
    assert result["count"] == 3
    kinds = [r["kind"] for r in result["references"]]
    assert "definition (function)" in kinds
    assert "import" in kinds
    assert "call" in kinds

def test_find_references_zero(repo_fixture):
    # 3. zero references
    result = json.loads(find_references(repo_fixture, "non_existent_func"))
    assert result["count"] == 0
    assert result["references"] == []

def test_find_references_class(repo_fixture):
    # 5. method/class reference
    result = json.loads(find_references(repo_fixture, "MyClass"))
    assert result["count"] == 3
    kinds = [r["kind"] for r in result["references"]]
    assert "definition (class)" in kinds
    assert "import" in kinds
    assert "call" in kinds

def test_find_references_invalid_symbol(repo_fixture):
    # 6. invalid symbol
    result = json.loads(find_references(repo_fixture, ""))
    assert "error" in result

def test_find_references_invalid_path(repo_fixture):
    # 7. invalid path
    result = json.loads(find_references(repo_fixture, "MyClass", "does_not_exist.py"))
    assert "error" in result

def test_find_references_boundary(repo_fixture):
    # 8. repository boundary protection
    result = json.loads(find_references(repo_fixture, "MyClass", "../outside.py"))
    assert "error" in result
    assert "escapes repository" in result["error"]

def test_run_linter_issues(repo_fixture):
    # 1. file with lint issue (utils.py has unused variable)
    result = json.loads(run_linter(repo_fixture, "utils.py"))
    assert result["success"] is True
    assert result["issue_count"] >= 1
    assert any(issue["code"] == "F841" for issue in result["issues"])  # F841 is unused variable in ruff

def test_run_linter_clean(repo_fixture):
    # 2. clean file (main.py is mostly clean, but let's just check it doesn't fail)
    result = json.loads(run_linter(repo_fixture, "main.py"))
    assert result["success"] is True
    # It might have D100 (missing docstring), but we know success is True

def test_run_linter_nonexistent(repo_fixture):
    # 3. nonexistent file
    result = json.loads(run_linter(repo_fixture, "missing.py"))
    assert result["success"] is False
    assert result["error"]["type"] == "ValidationError"

def test_run_linter_invalid_path(repo_fixture):
    # 4. invalid path / 8. repository boundary protection
    result = json.loads(run_linter(repo_fixture, "../outside.py"))
    assert result["success"] is False
    assert result["error"]["type"] == "ValidationError"
    assert "escapes repository" in result["error"]["message"]

def test_run_linter_unsupported(repo_fixture):
    # 5. unsupported file
    result = json.loads(run_linter(repo_fixture, "non_python.txt"))
    assert result["success"] is False
    assert result["error"]["type"] == "UnsupportedFile"

def test_run_linter_process_failure(repo_fixture, monkeypatch):
    # 6. linter process failure (e.g. command not found)
    import subprocess
    def mock_run(*args, **kwargs):
        raise FileNotFoundError("ruff not found")
    monkeypatch.setattr(subprocess, "run", mock_run)
    result = json.loads(run_linter(repo_fixture, "main.py"))
    assert result["success"] is False
    assert result["error"]["type"] == "InternalError"

def test_run_linter_parse_failure(repo_fixture, monkeypatch):
    # 7. structured output parsing
    import subprocess
    class MockResult:
        returncode = 0
        stdout = "not json"
    def mock_run(*args, **kwargs):
        return MockResult()
    monkeypatch.setattr(subprocess, "run", mock_run)
    result = json.loads(run_linter(repo_fixture, "main.py"))
    assert result["success"] is False
    assert result["error"]["type"] == "ParseFailed"
