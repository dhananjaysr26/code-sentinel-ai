"""Unit tests for the DiffParser."""
import pytest
from sentinel.services.diff_parser import DiffParser
from sentinel.schemas.diff import ParsedDiff

SIMPLE_DIFF = """\
diff --git a/src/user.py b/src/user.py
index abc1234..def5678 100644
--- a/src/user.py
+++ b/src/user.py
@@ -10,4 +10,4 @@ class User:
     def get_email(self):
-        return None
+        return self.email
     
     def get_name(self):
"""

ADD_FILE_DIFF = """\
diff --git a/src/new_file.py b/src/new_file.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/src/new_file.py
@@ -0,0 +1,2 @@
+def greet():
+    return "hello"
"""

DELETE_FILE_DIFF = """\
diff --git a/src/old_file.py b/src/old_file.py
deleted file mode 100644
index 1234567..0000000
--- a/src/old_file.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def old():
-    pass
"""

MULTI_FILE_DIFF = """\
diff --git a/a.py b/a.py
index 1111111..2222222 100644
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
-x = 1
+x = 2
 y = 3
diff --git a/b.py b/b.py
index 3333333..4444444 100644
--- a/b.py
+++ b/b.py
@@ -5,2 +5,2 @@
 def foo():
-    return None
+    return 0
"""

parser = DiffParser()

def test_empty_diff_returns_empty_result():
    result = parser.parse("")
    assert isinstance(result, ParsedDiff)
    assert result.changed_files == []
    assert result.total_hunks == 0
    assert result.raw_diff == ""

def test_whitespace_only_diff_returns_empty():
    result = parser.parse("   \n  ")
    assert result.changed_files == []

def test_single_file_single_hunk_parsed():
    result = parser.parse(SIMPLE_DIFF)
    assert len(result.changed_files) == 1
    assert result.total_hunks == 1
    file = result.changed_files[0]
    assert file.path == "src/user.py"
    assert len(file.hunks) == 1

def test_hunk_line_counts():
    result = parser.parse(SIMPLE_DIFF)
    hunk = result.changed_files[0].hunks[0]
    assert hunk.new_start == 10
    assert hunk.old_start == 10

def test_added_lines_extracted():
    result = parser.parse(SIMPLE_DIFF)
    hunk = result.changed_files[0].hunks[0]
    assert any("self.email" in line for line in hunk.added_lines)

def test_removed_lines_extracted():
    result = parser.parse(SIMPLE_DIFF)
    hunk = result.changed_files[0].hunks[0]
    assert any("None" in line for line in hunk.removed_lines)

def test_new_file_detected():
    result = parser.parse(ADD_FILE_DIFF)
    assert len(result.changed_files) == 1
    file = result.changed_files[0]
    assert file.is_new is True
    assert file.path == "src/new_file.py"

def test_deleted_file_detected():
    result = parser.parse(DELETE_FILE_DIFF)
    assert len(result.changed_files) == 1
    file = result.changed_files[0]
    assert file.is_deleted is True

def test_multi_file_diff():
    result = parser.parse(MULTI_FILE_DIFF)
    assert len(result.changed_files) == 2
    assert result.total_hunks == 2
    paths = {f.path for f in result.changed_files}
    assert "a.py" in paths
    assert "b.py" in paths

def test_hunk_text_non_empty():
    result = parser.parse(SIMPLE_DIFF)
    hunk = result.changed_files[0].hunks[0]
    assert len(hunk.hunk_text) > 0
    assert "@@ " in hunk.hunk_text

def test_changed_line_numbers_populated():
    result = parser.parse(SIMPLE_DIFF)
    hunk = result.changed_files[0].hunks[0]
    assert len(hunk.changed_line_numbers) >= 1
