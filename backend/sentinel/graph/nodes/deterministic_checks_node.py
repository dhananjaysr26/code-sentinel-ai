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
            logger.warning(f"Linter execution failed for {path}: {exc}")
            
    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info(f"DETERMINISTIC_FINDINGS count={len(findings)}")
    
    return {"deterministic_raw_findings": findings}
