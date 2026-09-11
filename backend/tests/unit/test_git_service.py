"""Unit tests for GitService."""
import subprocess
import pytest
from sentinel.services.git_service import GitService, GitServiceError


def test_nonexistent_path_raises_value_error(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        GitService(tmp_path / "no_such_dir")


def test_non_git_directory_raises_value_error(tmp_path):
    non_git = tmp_path / "plain_dir"
    non_git.mkdir()
    with pytest.raises(ValueError, match="Not a git repository"):
        GitService(non_git)


def test_valid_repo_initializes(temp_git_repo):
    svc = GitService(temp_git_repo)
    assert svc.repo_path == temp_git_repo.resolve()


def test_validate_ref_head_is_valid(temp_git_repo):
    svc = GitService(temp_git_repo)
    assert svc.validate_ref("HEAD") is True


def test_validate_ref_invalid_returns_false(temp_git_repo):
    svc = GitService(temp_git_repo)
    assert svc.validate_ref("nonexistent-branch-xyz") is False


def test_get_diff_returns_string(temp_git_repo):
    svc = GitService(temp_git_repo)
    diff = svc.get_diff("HEAD~1", "HEAD")
    assert isinstance(diff, str)
    assert len(diff) > 0  # there should be changes


def test_get_diff_empty_when_no_changes(temp_git_repo):
    svc = GitService(temp_git_repo)
    diff = svc.get_diff("HEAD", "HEAD")
    assert diff == ""


def test_get_changed_files(temp_git_repo):
    svc = GitService(temp_git_repo)
    files = svc.get_changed_files("HEAD~1", "HEAD")
    assert "app.py" in files


def test_read_file_lines_valid(temp_git_repo):
    svc = GitService(temp_git_repo)
    content = svc.read_file_lines("README.md", 1, 1)
    assert "Test repo" in content


def test_read_file_lines_invalid_start(temp_git_repo):
    svc = GitService(temp_git_repo)
    with pytest.raises(ValueError, match="start_line"):
        svc.read_file_lines("README.md", 0, 1)


def test_read_file_lines_end_before_start(temp_git_repo):
    svc = GitService(temp_git_repo)
    with pytest.raises(ValueError, match="end_line"):
        svc.read_file_lines("README.md", 5, 3)


def test_read_file_path_traversal_blocked(temp_git_repo):
    svc = GitService(temp_git_repo)
    with pytest.raises(GitServiceError, match="escapes repository root"):
        svc.read_file_lines("../../../etc/passwd", 1, 5)
