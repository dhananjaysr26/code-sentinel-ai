with open("backend/sentinel/graph/state.py", "r") as f:
    content = f.read()

if "evidence_package" not in content:
    content = content.replace(
        'context_blocks: list[ContextBlock]', 
        'context_blocks: list[ContextBlock]\n    evidence_package: dict'
    )
    with open("backend/sentinel/graph/state.py", "w") as f:
        f.write(content)
