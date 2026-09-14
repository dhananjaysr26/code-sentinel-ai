import logging
import time
import json
from pathlib import Path

from django.conf import settings

from sentinel.graph.state import ReviewState
from sentinel.mcp.client import StdioMCPClient
from sentinel.schemas.findings import Finding, Severity, Category, Source

logger = logging.getLogger(__name__)

async def deterministic_checks_node(state: ReviewState) -> dict:
    start = time.monotonic()
    repo_path = state.get("repo_path")
    diff_hunks = state.get("diff_hunks", [])
    
    if not diff_hunks:
        return {"raw_findings": []}
        
    server_script = str(Path(settings.MCP_SERVER_SCRIPT).resolve())
    mcp_client = StdioMCPClient(server_script=server_script)
    
    # Build a map of file_path -> set of changed lines
    changed_lines_map = {}
    for hunk in diff_hunks:
        if hunk.file_path.endswith(".py"):
            if hunk.file_path not in changed_lines_map:
                changed_lines_map[hunk.file_path] = set()
            changed_lines_map[hunk.file_path].update(hunk.changed_line_numbers)
    
    findings = []
    
    for path, changed_lines in changed_lines_map.items():
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
            logger.warning(f"Linter execution failed for {path}: {exc}")
            
    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info(f"DETERMINISTIC_FINDINGS count={len(findings)}")
    
    return {"deterministic_raw_findings": findings}
