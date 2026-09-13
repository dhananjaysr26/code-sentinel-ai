import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

# Make it conditional
replacement = """
            # Compress older tool results to save tokens (Selective Context Management)
            if getattr(settings, "USE_CONTEXT_ENGINEERING", True):
                messages = relevance_aware_compaction(messages)
            
            # Inject context manifest
            if getattr(settings, "USE_CONTEXT_ENGINEERING", True):
                manifest = generate_context_manifest(evidence_store, specialist)
                current_messages = list(messages)
                if isinstance(current_messages[0], SystemMessage):
                    current_messages[0] = SystemMessage(content=system_prompt + "\\n\\n" + manifest)
            else:
                current_messages = list(messages)
"""

content = re.sub(
    r'            # Compress older tool results to save tokens \(Selective Context Management\)[\s\S]*?manifest \+ "\\n"\)  # fixed parsing issue',
    replacement.strip(),
    content
)
# Wait, my regex above probably won't match correctly. Let's do a direct replacement.
