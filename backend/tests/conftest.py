"""
Pytest configuration for CodeSentinel AI backend tests.
"""
import os
import subprocess
import pytest

# Set Django settings module before any imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a minimal temporary git repository for testing.
    
    Yields the path to the initialized repo.
    """
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir, check=True, capture_output=True,
    )

    # Create initial commit
    (repo_dir / "README.md").write_text("# Test repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo_dir, check=True, capture_output=True,
    )

    # Create a second commit with a Python file change
    (repo_dir / "app.py").write_text("def hello():\n    pass\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add app.py"],
        cwd=repo_dir, check=True, capture_output=True,
    )

    yield repo_dir
