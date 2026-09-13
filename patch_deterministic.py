import re
with open("backend/sentinel/graph/nodes/deterministic_checks_node.py", "r") as f:
    content = f.read()

old_loop = """    for path, changed_lines in changed_lines_map.items():
        try:
            result = await mcp_client.run_linter(repo_path, path)
            data = json.loads(result)
            issues = data.get("issues", [])
            
            for issue in issues:
                issue_line = issue.get("line")
                # Only report linter issues introduced or touched by this change
                # (Filter against the diff)
                if issue_line in changed_lines:
                    findings.append(Finding(
                        file=path,
                        line=issue_line,
                        title=f"Linter warning: {issue.get('message', '')}",
                        category=Category.CODE_QUALITY,
                        severity=Severity.MEDIUM,
                        confidence=1.0,
                        explanation=f"Linter rule {issue.get('code')}: {issue.get('message')}",
                        evidence=f"Detected by {data.get('tool')}",
                        source=Source.LINTER,
                        reviewer="deterministic",
                        subcategory=issue.get("code")
                    ).model_dump())
        except Exception as exc:
            logger.warning(f"Linter execution failed for {path}: {exc}")"""

new_loop = """    for path, changed_lines in changed_lines_map.items():
        try:
            base_ref = state.get("base_ref", "HEAD~1")
            
            # 1. Lint the base revision
            base_result = await mcp_client.run_linter(repo_path, path, revision=base_ref)
            base_data = json.loads(base_result)
            base_issues = { (i.get("line"), i.get("code")) for i in base_data.get("issues", []) }
            
            # 2. Lint the target working tree
            result = await mcp_client.run_linter(repo_path, path)
            data = json.loads(result)
            issues = data.get("issues", [])
            
            for issue in issues:
                issue_line = issue.get("line")
                issue_code = issue.get("code")
                
                # Report if it's NEW in this diff
                if (issue_line, issue_code) not in base_issues:
                    # Severity mapping
                    code_lower = str(issue_code).lower()
                    if code_lower.startswith("f4") or code_lower.startswith("e") or code_lower.startswith("w"):
                        sev = Severity.LOW
                    else:
                        sev = Severity.MEDIUM
                        
                    findings.append(Finding(
                        file=path,
                        line=issue_line,
                        title=f"Linter warning: {issue.get('message', '')}",
                        category=Category.CODE_QUALITY,
                        severity=sev,
                        confidence=1.0,
                        explanation=f"Linter rule {issue.get('code')}: {issue.get('message')}",
                        evidence=f"Detected by {data.get('tool')}",
                        source=Source.LINTER,
                        reviewer="deterministic",
                        subcategory=issue.get("code")
                    ).model_dump())
        except Exception as exc:
            logger.warning(f"Linter execution failed for {path}: {exc}")"""

content = content.replace(old_loop, new_loop)

with open("backend/sentinel/graph/nodes/deterministic_checks_node.py", "w") as f:
    f.write(content)
