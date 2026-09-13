with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

replacement = """
            existing_latencies = dict(state.get("reviewer_latencies", {}))
            existing_latencies[f"{specialist}_ms"] = r_latency
            existing_latencies[f"{specialist}_loop"] = {
                "specialist_name": specialist,
                "llm_call_count": 1,
                "tool_call_count": 0,
                "iteration_count": 0,
                "tools_used": [],
                "context_files_retrieved": [],
                "stop_reason": "sufficient_from_diff_fast_path",
                "total_latency_ms": r_latency,
                "finding_count": len(final_findings)
            }
            
            event_dict = {
                "node": specialist,
                "event": "llm_call",
                "details": "invoke_structured (fast_path)",
                "latency_ms": r_latency,
                "tokens": s_dict.get("total_tokens", 0)
            }
            
            if review_id:
                from datetime import datetime, timezone
                try:
                    from sentinel.services.events import publish_event
                    sse_event = {
                        "review_id": review_id,
                        "reviewer": specialist,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        **event_dict
                    }
                    publish_event(review_id, sse_event)
                except ImportError:
                    pass
            
            return {
                f"{specialist}_raw_findings": final_findings,
                "llm_usages": [s_dict],
                "reviewer_latencies": existing_latencies,
                "timeline": [event_dict],
"""

import re
# Find the block we want to replace
content = re.sub(r'existing_latencies = dict\(state\.get\("reviewer_latencies", \{\}\)\).*?"timeline": \[\{"node": specialist, "event": "llm_call", "details": "invoke_structured \(fast_path\)", "latency_ms": r_latency, "tokens": s_dict\.get\("total_tokens", 0\)\}\],', replacement, content, flags=re.DOTALL)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
