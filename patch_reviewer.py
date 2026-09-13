import re
with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

# Change human_content builder
old_human_content_1 = """    human_content += "### INITIAL CODE CHANGES\\n\\n"
    for block in blocks:
        human_content += f"File: {block.file_path}\\n"
        human_content += f"```python\\n{block.surrounding_code}\\n```\\n"
        human_content += f"Diff:\\n```diff\\n{block.hunk_diff}\\n```\\n\\n\""""

new_human_content_1 = """    human_content += "### INITIAL CODE CHANGES\\n\\n"
    # To save tokens, we only provide the raw diff hunks here, partitioned by review units.
    # The agent must use read_file if it needs surrounding context.
    evidence_package = state.get("evidence_package", {})
    review_units = evidence_package.get("review_units", [])
    relevant_files = [u["file"] for u in review_units if specialist in u.get("categories", [])]
    
    if review_units and relevant_files:
        human_content += f"Note: This is a large diff. You are only seeing files categorized for {specialist} analysis.\\n\\n"
    
    for block in blocks:
        if review_units and block.file_path not in relevant_files:
            continue
        human_content += f"File: {block.file_path}\\n"
        human_content += f"Diff:\\n```diff\\n{block.hunk_diff}\\n```\\n\\n\""""

content = content.replace(old_human_content_1, new_human_content_1)

# In final_messages, do NOT include human_content again, just closing_msg is enough, 
# or a much smaller human_content. Actually relevance_aware_compaction preserves the System and Human messages (which are indices 0 and 1)
# So final_messages already has the compacted history!
# Wait, look at this:
old_final_messages = """            final_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content),
                closing_msg
            ]"""

new_final_messages = """            # Because relevance_aware_compaction returns a compacted version of the entire history,
            # we should just append closing_msg to it!
            final_messages = messages + [closing_msg]"""

content = content.replace(old_final_messages, new_final_messages)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
