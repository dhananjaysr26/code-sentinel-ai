from sentinel.graph.context_engineering import generate_context_manifest, EvidenceItem

store = [
    EvidenceItem(
        reviewer="security",
        source="read_file",
        path="src/api.py",
        evidence_type="code",
        summary="read api",
        content="def api(): pass"
    )
]

print(generate_context_manifest(store, reviewer="security", include_content=True))
