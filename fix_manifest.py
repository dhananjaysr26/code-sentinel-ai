import re
with open("backend/sentinel/graph/context_engineering.py", "r") as f:
    content = f.read()

content = content.replace("def generate_context_manifest(evidence_store: List[EvidenceItem]) -> str:", "def generate_context_manifest(evidence_store: List[EvidenceItem], reviewer: str = None) -> str:")
content = content.replace(
    '    for ev in evidence_store:',
    '    for ev in evidence_store:\n        if reviewer and ev.reviewer != reviewer:\n            continue'
)

with open("backend/sentinel/graph/context_engineering.py", "w") as f:
    f.write(content)

# Now update iterative_reviewer.py to pass the reviewer
with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

content = content.replace("generate_context_manifest(evidence_store)", "generate_context_manifest(evidence_store, specialist)")

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
