import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

# Replace Branch B
branch_b_replacement = """        # ── Branch B: No tool calls — extract final findings ──────────────────
        logger.info(
            "SPECIALIST_FINISHED_TOOLS specialist=%s at iteration %d — forcing final structured output",
            specialist, iteration,
        )
        _compress_message_history(messages)
        
        try:
            t_final = time.monotonic()
            closing_msg = HumanMessage(
                content="Based on all the context retrieved above, now provide your final findings as JSON. Return ONLY the JSON object."
            )
            final_messages = messages + [response, closing_msg] if getattr(response, "content", "") else messages + [closing_msg]
            
            structured_result = await invoke_structured(
                provider, final_messages, ReviewFindings
            )
            r_latency = int((time.monotonic() - t_final) * 1000)
            llm_latency_ms += r_latency
            
            s_usage = structured_result.usage
            s_usage.reviewer = specialist
            s_dict = s_usage.model_dump()
            s_dict["iteration"] = iteration
            s_dict["llm_call_number"] = llm_call_count + 1
            new_usages.append(s_dict)
            llm_call_count += 1
            
            _add_event({
                "node": specialist,
                "event": "llm_call",
                "details": "invoke_structured (final)",
                "latency_ms": r_latency,
                "tokens": s_dict.get("total_tokens", 0)
            })

            final_findings = []
            if structured_result.response:
                for f in structured_result.response.findings:
                    d = f.model_dump()
                    d["reviewer"] = specialist
                    d.setdefault("source", "llm")
                    final_findings.append(d)
            findings = final_findings
            stop_reason = "final_result"
        except Exception as exc:
            logger.error("Final structured extraction failed: %s", exc)
            stop_reason = "provider_error"
            
        break"""

content = re.sub(
    r'        # ── Branch B: No tool calls — extract final findings ──────────────────.*?        break',
    branch_b_replacement,
    content,
    flags=re.DOTALL
)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
