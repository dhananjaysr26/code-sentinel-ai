import re

with open("backend/sentinel/graph/context_engineering.py", "r") as f:
    content = f.read()

replacement = """def generate_context_manifest(evidence_store: List[EvidenceItem], reviewer: str = None, include_content: bool = False) -> str:
    \"\"\"Generates a compact summary of retrieved evidence to inject into LLM prompt.\"\"\"
    if not evidence_store:
        return "No additional evidence retrieved yet."
    
    lines = ["### COMPACT CONTEXT MANIFEST"]
    for ev in evidence_store:
        if reviewer and ev.reviewer != reviewer:
            continue
        loc = f"{ev.path}"
        if ev.line_start and ev.line_end:
            loc += f" (lines {ev.line_start}-{ev.line_end})"
        if ev.symbol:
            loc += f" [symbol: {ev.symbol}]"
        
        lines.append(f"- ID: {ev.evidence_id} | {loc} | {ev.summary}")
        if include_content:
            lines.append("```")
            lines.append(ev.content)
            lines.append("```\\n")
            
    if not include_content:
        lines.append("\\n(Raw content stored in evidence_store. Re-fetch via MCP only if new details are needed).")
    return "\\n".join(lines)"""

content = re.sub(r'def generate_context_manifest[\s\S]*?return "\\n"\.join\(lines\)', replacement, content)

with open("backend/sentinel/graph/context_engineering.py", "w") as f:
    f.write(content)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

# Make final structured output include the content
content = content.replace("compact_manifest = generate_context_manifest(evidence_store)", "compact_manifest = generate_context_manifest(evidence_store, specialist, include_content=True)")

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
