import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

# 1. Update Tool Schemas to require `justification`
replacement_tools = """class ReadFileArgs(BaseModel):
    file_path: str = Field(description="The path to the file to read, e.g. 'src/main.py'")
    start_line: Optional[int] = Field(None, description="The starting line number to read (inclusive)")
    end_line: Optional[int] = Field(None, description="The ending line number to read (inclusive)")
    justification: str = Field(description="Why do you need to read this file? (e.g. 'To check caller logic')")

class FindReferencesArgs(BaseModel):
    symbol: str = Field(description="The function, class, or variable name to search for.")
    justification: str = Field(description="Why do you need to find this symbol?")
"""
content = re.sub(r'class ReadFileArgs.*?description="The function, class, or variable name to search for."\)\n', replacement_tools, content, flags=re.DOTALL)

# 2. Add fast-path for sufficient_from_diff
fast_path = """
    provider = state["llm_provider"]
    evidence_package = state.get("evidence_package", {})
    context_decisions = evidence_package.get("context_decisions", {})
    
    all_sufficient = False
    if context_decisions:
        all_sufficient = all(d.get("decision") == "sufficient_from_diff" for d in context_decisions.values())
    elif not context_decisions and len(raw_diff.splitlines()) < 100:
        all_sufficient = True
        
    if all_sufficient:
        logger.info("SPECIALIST_FAST_PATH specialist=%s — context is sufficient_from_diff. Bypassing tool loop.", specialist)
        t_final = time.monotonic()
        manifest = generate_context_manifest(evidence_store, specialist, include_content=True)
        final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\\n\\n{manifest}\\n\\nNote: The Diff was marked as sufficient. Please analyze the diff."
        final_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_content),
            HumanMessage(content=final_package_prompt)
        ]
        
        try:
            structured_result = await invoke_structured(provider, final_messages, ReviewFindings)
            r_latency = int((time.monotonic() - t_final) * 1000)
            
            s_dict = structured_result.usage.model_dump() if structured_result.usage else {}
            s_dict["reviewer"] = specialist
            s_dict["iteration"] = 0
            s_dict["llm_call_number"] = 1
            s_dict.update(compute_token_breakdown(final_messages))
            
            final_findings = []
            if structured_result.response:
                for f in structured_result.response.findings:
                    d = f.model_dump()
                    d["reviewer"] = specialist
                    d.setdefault("source", "llm")
                    final_findings.append(d)
                    
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
            
            return {
                f"{specialist}_raw_findings": final_findings,
                "llm_usages": [s_dict],
                "reviewer_latencies": existing_latencies,
                "timeline": [{"node": specialist, "event": "llm_call", "details": "invoke_structured (fast_path)", "latency_ms": r_latency, "tokens": s_dict.get("total_tokens", 0)}],
                "llm_latency_ms": r_latency,
            }
        except Exception as exc:
            logger.error("Fast path structured extraction failed: %s", exc)

"""
# Find where provider is set, and insert fast_path
content = content.replace('provider = state["llm_provider"]', fast_path)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)

