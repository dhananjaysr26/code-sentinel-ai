import pytest
from sentinel.graph.context_planner import run_context_planner

def test_planner_simple_rename():
    diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,3 +1,3 @@
 def hello():
-    msg = "world"
+    message = "world"
     return message
"""
    evidence = run_context_planner(diff, ["test.py"])
    unit = evidence.review_units[0]
    assert unit.decision == "sufficient_from_diff"
    assert "correctness" in unit.categories
    assert "security" not in unit.categories

def test_planner_sql_injection():
    diff = """diff --git a/utils.py b/utils.py
--- a/utils.py
+++ b/utils.py
@@ -10,3 +10,3 @@
 def get_user(user_id):
-    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
+    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
     return cursor.fetchone()
"""
    # This is a small, single-file diff, but contains a high-risk security signal
    evidence = run_context_planner(diff, ["utils.py"])
    unit = evidence.review_units[0]
    # It must NOT be sufficient_from_diff because of security score >= 2
    assert unit.decision == "requires_cross_file_context"
    assert "security" in unit.categories
    assert "sql_operation" in unit.risk_signals

def test_planner_auth_bypass():
    diff = """diff --git a/service.py b/service.py
--- a/service.py
+++ b/service.py
@@ -1,3 +1,3 @@
 def delete_account(user):
-    if user.is_admin:
+    if user.is_active:
         db.delete(user)
"""
    evidence = run_context_planner(diff, ["service.py"])
    unit = evidence.review_units[0]
    # is_admin is an authorization keyword
    assert "security" in unit.categories
    assert unit.decision == "requires_cross_file_context"
    assert "authorization" in unit.risk_signals

def test_planner_eval_injection():
    diff = """diff --git a/index.js b/index.js
--- a/index.js
+++ b/index.js
@@ -1,3 +1,3 @@
 function process(input) {
-    return JSON.parse(input);
+    return eval(input);
 }
"""
    evidence = run_context_planner(diff, ["index.js"])
    unit = evidence.review_units[0]
    assert unit.decision == "requires_cross_file_context"
    assert "security" in unit.categories
    assert "command_execution" in unit.risk_signals

def test_planner_public_signature_change():
    diff = """diff --git a/api.py b/api.py
--- a/api.py
+++ b/api.py
@@ -1,3 +1,3 @@
-def fetch_data(user_id: int) -> dict:
+def fetch_data(user_id: str) -> list:
     pass
"""
    evidence = run_context_planner(diff, ["api.py"])
    unit = evidence.review_units[0]
    assert unit.decision == "requires_cross_file_context"
    assert "api_or_contract" in unit.risk_signals
