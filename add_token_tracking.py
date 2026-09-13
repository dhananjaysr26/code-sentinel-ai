import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

content = content.replace("from sentinel.graph.context_engineering import (", "from sentinel.graph.context_engineering import (\n    compute_token_breakdown,")

tracking_code = """
            s_dict["iteration"] = iteration
            s_dict["llm_call_number"] = llm_call_count + 1
            breakdown = compute_token_breakdown(final_messages)
            s_dict.update(breakdown)
            new_usages.append(s_dict)"""

content = content.replace('            s_dict["iteration"] = iteration\n            s_dict["llm_call_number"] = llm_call_count + 1\n            new_usages.append(s_dict)', tracking_code)

tracking_code_fallback = """
                repair_dict["iteration"] = iteration
                repair_dict["llm_call_number"] = llm_call_count + 1
                breakdown = compute_token_breakdown(final_messages)
                repair_dict.update(breakdown)
                new_usages.append(repair_dict)"""

content = content.replace('                repair_dict["iteration"] = iteration\n                repair_dict["llm_call_number"] = llm_call_count + 1\n                new_usages.append(repair_dict)', tracking_code_fallback)

tracking_code_loop = """
            usage_dict["iteration"] = iteration
            usage_dict["llm_call_number"] = llm_call_count
            breakdown = compute_token_breakdown(current_messages)
            usage_dict.update(breakdown)
            new_usages.append(usage_dict)"""

content = content.replace('            usage_dict["iteration"] = iteration\n            usage_dict["llm_call_number"] = llm_call_count\n            new_usages.append(usage_dict)', tracking_code_loop)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
