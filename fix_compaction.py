import re

with open("backend/sentinel/graph/context_engineering.py", "r") as f:
    content = f.read()

compaction_replacement = """def relevance_aware_compaction(messages: List[BaseMessage]) -> List[BaseMessage]:
    \"\"\"
    Compacts messages by keeping:
    - Initial task (System, Human)
    - Replaces all ToolMessages with placeholders, as their content is injected via Context Manifest.
    \"\"\"
    if len(messages) <= 2:
        return messages
        
    compacted = []
    # Always keep system and initial user message
    compacted.append(messages[0])
    compacted.append(messages[1])
    
    for msg in messages[2:]:
        if isinstance(msg, ToolMessage):
            compact_msg = ToolMessage(
                content="[CONTENT COMPACTED - Recorded in Context Manifest above]",
                tool_call_id=msg.tool_call_id,
                name=msg.name
            )
            compacted.append(compact_msg)
        else:
            compacted.append(msg)
            
    return compacted"""

content = re.sub(r'def relevance_aware_compaction[\s\S]*?return compacted', compaction_replacement, content)

with open("backend/sentinel/graph/context_engineering.py", "w") as f:
    f.write(content)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

content = content.replace("manifest = generate_context_manifest(evidence_store, specialist)", "manifest = generate_context_manifest(evidence_store, specialist, include_content=True)")

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
