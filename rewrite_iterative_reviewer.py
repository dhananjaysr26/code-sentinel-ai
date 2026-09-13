import re

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "r") as f:
    content = f.read()

imports = """
from sentinel.graph.context_engineering import (
    normalize_evidence,
    generate_context_manifest,
    relevance_aware_compaction,
    generate_evidence_cache_key,
    EvidenceItem
)
"""

content = content.replace("from sentinel.services.llm_service import invoke_structured, get_llm, _normalize_usage", "from sentinel.services.llm_service import invoke_structured, get_llm, _normalize_usage" + imports)

# Remove old _compress_message_history
content = re.sub(r'def _compress_message_history\(messages\):[\s\S]*?(?=def run_iterative_reviewer)', '', content)

# 1. Initialize evidence_store
content = content.replace(
    'tool_cache = state.get("tool_cache", {})',
    'tool_cache = state.get("tool_cache", {})\n    evidence_store = state.get("evidence_store", [])'
)

# 2. Update cache key generator
content = content.replace(
    'global_cache_key = f"{cache_ref}:{key}"',
    'global_cache_key = generate_evidence_cache_key(cache_ref, tool_name, tool_args)'
)

# 3. Add to evidence store on tool execution
tool_execution_code = """                    try:
                        tool_result = await _execute_tool(mcp_client, tool_name, tool_args, repo_path)
                        tool_cache[global_cache_key] = tool_result
                        
                        # Normalize and store evidence
                        evidence_item = normalize_evidence(tool_name, tool_args, tool_result, specialist)
                        evidence_store.append(evidence_item)
                        
                    except Exception as tool_exc:"""
content = re.sub(r'                    try:\s+tool_result = await _execute_tool\(mcp_client, tool_name, tool_args, repo_path\)\s+tool_cache\[global_cache_key\] = tool_result\s+except Exception as tool_exc:', tool_execution_code, content)

# Also handle cache hit logic for evidence store
cache_hit_logic = """                    logger.info("MCP_TOOL_CACHE_HIT tool=%s specialist=%s", tool_name, specialist)
                    tool_result = tool_cache[global_cache_key]
                    cache_hit = True
                    mcp_calls += 1 # we still count it as a conceptual request
                    # But don't increment unique_mcp_calls
                    evidence_item = normalize_evidence(tool_name, tool_args, tool_result, specialist)
                    evidence_store.append(evidence_item)"""
content = re.sub(r'                    logger.info\("MCP_TOOL_CACHE_HIT tool=%s specialist=%s", tool_name, specialist\)\s+tool_result = tool_cache\[global_cache_key\]\s+cache_hit = True\s+mcp_calls \+= 1 # we still count it as a conceptual request\s+# But don\'t increment unique_mcp_calls', cache_hit_logic, content)

# 4. Replace _compress_message_history with relevance_aware_compaction
content = content.replace('_compress_message_history(messages)', 'messages = relevance_aware_compaction(messages)')

# 5. Inject Context Manifest into system prompt inside the loop
# We can just append the manifest dynamically before LLM calls
loop_llm_call = """            
            # Inject context manifest
            manifest = generate_context_manifest(evidence_store)
            current_messages = list(messages)
            if isinstance(current_messages[0], SystemMessage):
                current_messages[0] = SystemMessage(content=system_prompt + "\\n\\n" + manifest)
                
            try:
                response = await safe_ainvoke(tool_llm, current_messages)"""
content = re.sub(r'            try:\s+response = await safe_ainvoke\(tool_llm, messages\)', loop_llm_call, content)

# 6. Final Structured Output optimization (give it compact evidence package)
final_package = """        try:
            t_final = time.monotonic()
            
            # Create a compact evidence package for final extraction
            compact_manifest = generate_context_manifest(evidence_store)
            final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\\n\\n{compact_manifest}"
            closing_msg = HumanMessage(content=final_package_prompt)
            
            # Do not send the entire ReAct transcript
            final_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content),
                closing_msg
            ]
            
            structured_result = await invoke_structured("""
content = re.sub(r'        try:\s+t_final = time.monotonic\(\)\s+closing_msg = HumanMessage\(\s+content="Based on all the context retrieved above, now provide your final findings as JSON. Return ONLY the JSON object."\s+\)\s+final_messages = messages\s+structured_result = await invoke_structured\(', final_package, content)

fallback_package = """        try:
            fallback_count += 1
            t_llm_start = time.monotonic()
            
            compact_manifest = generate_context_manifest(evidence_store)
            final_package_prompt = f"Based on the following retrieved evidence, provide your final structured findings:\\n\\n{compact_manifest}"
            
            final_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content),
                HumanMessage(content=final_package_prompt)
            ]
            
            repair_result = await invoke_structured(provider, final_messages, ReviewFindings)"""
content = re.sub(r'        try:\s+fallback_count \+= 1\s+t_llm_start = time.monotonic\(\)\s+closing_msg = HumanMessage\(\s+content="Based on all the context retrieved above, now provide your final findings as JSON. Return ONLY the JSON object."\s+\)\s+repair_result = await invoke_structured\(provider, messages, ReviewFindings\)', fallback_package, content)

with open("backend/sentinel/graph/nodes/iterative_reviewer.py", "w") as f:
    f.write(content)
