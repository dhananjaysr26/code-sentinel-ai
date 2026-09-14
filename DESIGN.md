# CodeSentinel AI — Architecture & Design

## Purpose

CodeSentinel AI is an AI-powered code review platform that accepts a local Git
repository and a revision range, runs a structured correctness analysis through
a LangGraph agent, and returns machine-readable findings. The MVP implements a
single vertical slice from Git diff to UI feedback.

---

## Architecture Overview

```mermaid
flowchart TD
    %% Node Styling
    classDef start_end fill:#f9f9f9,stroke:#333,stroke-width:2px,color:#333
    classDef deterministic fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#333
    classDef react_agent fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#333
    classDef mcp_sys fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,color:#333
    classDef data_flow fill:#fff3e0,stroke:#f57c00,stroke-width:1px,color:#333,stroke-dasharray: 5 5

    %% Graph Nodes
    START((START)):::start_end
    END_NODE((END)):::start_end

    subgraph Preparation Phase ["Phase 1: Preparation (Deterministic)"]
        ParseDiff[parse_diff<br/>Extract Hunks & Lines]:::deterministic
        
        subgraph PlanScope ["plan_and_scope_context"]
            Planner[Context Planner<br/>Risk Scoring & Decision]:::deterministic
            Partition[Partition Diff into<br/>Scoped Review Units]:::deterministic
        end
    end

    subgraph Specialist Phase ["Phase 2: Specialist Execution (Parallel)"]
        direction LR
        Correctness[Correctness Reviewer<br/>LangChain ReAct Agent]:::react_agent
        Security[Security Reviewer<br/>LangChain ReAct Agent]:::react_agent
        Linter[Diff-Aware Ruff Linter<br/>Deterministic Checker]:::deterministic
    end

    subgraph Retrieval Phase ["MCP Retrieval Infrastructure (On-Demand)"]
        MCPServer[MCP Server<br/>read_file, find_references, get_diff]:::mcp_sys
    end

    subgraph Consolidation Phase ["Phase 3: Consolidation (Deterministic)"]
        Merge[Merge Findings<br/>Combine Parallel Outputs]:::deterministic
        Dedupe[Deduplicate Findings<br/>Location & Category Match]:::deterministic
        Rank[Rank Findings<br/>Severity & Confidence]:::deterministic
        Validate[Validate Findings<br/>Zod Schema Gate]:::deterministic
    end

    subgraph Infrastructure ["Phase 4: Output & Persistence"]
        Persist[persist_review_result<br/>Django ORM]:::deterministic
        Return[return_structured_response<br/>HTTP API]:::deterministic
    end

    %% Data Flow Nodes
    ReviewUnits(("[Review Units & Context Decisions]")):::data_flow

    %% Edges
    START --> ParseDiff
    ParseDiff --> Planner
    Planner --> Partition
    Partition --> ReviewUnits
    
    ReviewUnits -->|Units categorized: correctness| Correctness
    ReviewUnits -->|Units categorized: security| Security
    ReviewUnits -->|Base vs Target refs| Linter
    
    %% MCP Tool Loop
    Correctness -.->|Tool request| MCPServer
    MCPServer -.->|Tool result| Correctness
    Security -.->|Tool request| MCPServer
    MCPServer -.->|Tool result| Security
    
    %% Output to Consolidation
    Correctness --> Merge
    Security --> Merge
    Linter --> Merge
    
    Merge --> Dedupe
    Dedupe --> Rank
    Rank --> Validate
    
    Validate --> Persist
    Persist --> Return
    Return --> END_NODE
```

*Note: Persistence and API response handling occur in the Django service after the LangGraph orchestration completion.*

### Context Engineering Components

To efficiently handle large diffs (e.g., 20k+ lines) without exceeding token limits or blowing up latency, the system relies on several advanced context engineering strategies:

1. **Deterministic Context Planner (`plan_and_scope_context`)**: 
   Rather than blindly feeding the entire diff or pre-fetching massive amounts of surrounding code upfront, the planner acts as a conservative heuristic engine. It evaluates the git diff for risk signals (`eval()`, `SQL`, `authorization` keywords, `open()`) and complexity. It decides whether the change can be evaluated on a fast-path (`sufficient_from_diff`), or if it requires cross-file MCP tool retrieval (`requires_cross_file_context`).

2. **Review-Unit Partitioning**:
   The monolithic git diff is split into file-scoped `ReviewUnit` payloads. The planner categorizes each unit (e.g., routing `auth.py` to the Security Agent, and `math.py` to the Correctness Agent). The downstream parallel agents receive **only** the scoped units assigned to their specialty. This massively reduces token bloat (e.g., dropping a 300k token review down to 65k tokens).

3. **Explicit Context-Retrieval via ReAct Tool Loop**:
   The graph does not imply that all context is always retrieved before the reviewers run. Instead, the context planner determines the expected context requirements, and the reviewers retrieve additional evidence through MCP only when necessary.
   - The LLM identifies missing context that may change the review conclusion.
   - Issues a `Tool request` (e.g., `read_file` or `find_references`).
   - Receives the `Tool result` from the MCP Server.
   - Continues reasoning to reach a final structured finding.
   
4. **Diff-Aware Baseline Linter**:
   Instead of reporting all static analysis warnings in a file, the deterministic linter node compares the `base_ref` against the `target_ref`, stripping out pre-existing technical debt to report *only* strictly new findings introduced by the commit.

5. **Merge, Deduplicate, and Rank Pipeline**:
   After the parallel execution, findings are consolidated. They undergo strict deduplication (to merge identical findings reported on adjacent lines) and are then ranked by Severity (CRITICAL > HIGH > MEDIUM > LOW) and Confidence, ensuring the most actionable signals are prioritized before returning the HTTP response.
6. **Instantaneous Cross-Agent MCP Tool Caching**:
   Because the `correctness_review` and `security_review` agents execute in parallel, there is a high probability they will request the same surrounding file context or cross-file references. To prevent redundant sub-process executions and latency spikes, the system uses a shared `tool_cache` in the LangGraph state. 
   - A deterministic hash is generated based on the target revision, tool name, and arguments.
   - If the Correctness agent reads `src/auth.py`, it immediately writes the result to the shared memory cache.
   - If the Security agent requests the same file moments later, it triggers an `MCP_TOOL_CACHE_HIT`, bypassing the MCP server entirely and instantly feeding the data back to the LLM.