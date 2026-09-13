import re
with open("backend/sentinel/graph/context_planner.py", "r") as f:
    content = f.read()

old_scores = """    for signal, pattern in SECURITY_PATTERNS.items():
        if pattern.search(text):
            risk_signals.append(signal)
            scores["security"] += 1"""

new_scores = """    for signal, pattern in SECURITY_PATTERNS.items():
        if pattern.search(text):
            risk_signals.append(signal)
            if signal == "command_execution":
                scores["security"] += 3
            elif signal == "sql_operation":
                scores["security"] += 2
            elif signal == "authorization":
                scores["security"] += 2
            else:
                scores["security"] += 1"""

content = content.replace(old_scores, new_scores)

with open("backend/sentinel/graph/context_planner.py", "w") as f:
    f.write(content)
