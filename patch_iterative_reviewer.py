import re
with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

old_human_content = """    evidence_package = state.get("evidence_package", {})
    review_units = evidence_package.get("review_units", [])
    relevant_files = [u["file"] for u in review_units if specialist in u.get("categories", [])]
    
    if review_units and relevant_files:
        human_content += f"Note: This is a large diff. You are only seeing files categorized for {specialist} analysis.\\n\\n"
    
    for block in blocks:
        if review_units and block.file_path not in relevant_files:
            continue
        human_content += f"File: {block.file_path}\\n"
        human_content += f"Diff:\\n```diff\\n{block.hunk_diff}\\n```\\n\\n\""""

new_human_content = """    evidence_package = state.get("evidence_package", {})
    review_units = evidence_package.get("review_units", [])
    relevant_units = [u for u in review_units if specialist in u.get("categories", [])]
    
    if review_units and relevant_units:
        human_content += f"Note: This diff has been partitioned. You are only seeing units categorized for {specialist} analysis.\\n\\n"
        for unit in relevant_units:
            human_content += f"File: {unit.get('file')}\\n"
            human_content += f"Risk Signals: {', '.join(unit.get('risk_signals', []))}\\n"
            human_content += f"Planner Decision: {unit.get('decision')}\\n"
            human_content += f"Diff:\\n```diff\\n{unit.get('diff')}\\n```\\n\\n"
    elif not review_units:
        human_content += f"Diff:\\n```diff\\n{state.get('raw_diff')}\\n```\\n\\n"
    else:
        human_content += f"No files were categorized as relevant for {specialist} analysis.\\n\\n\""""

content = content.replace(old_human_content, new_human_content)

old_fast_path = """    all_sufficient = False
    if context_decisions:
        all_sufficient = all(d.get("decision") == "sufficient_from_diff" for d in context_decisions.values())
    elif not context_decisions and raw_diff and len(raw_diff.splitlines()) < 100:
        all_sufficient = True"""

new_fast_path = """    all_sufficient = False
    if review_units and relevant_units:
        all_sufficient = all(u.get("decision") == "sufficient_from_diff" for u in relevant_units)
    elif not review_units and state.get("raw_diff") and len(state.get("raw_diff").splitlines()) < 100:
        all_sufficient = True"""

content = content.replace(old_fast_path, new_fast_path)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
