import re

with open('DESIGN.md', 'r') as f:
    content = f.read()

old_arch = """## Architecture Overview

```
User
  │
  ▼
React (TypeScript)
  │  POST /api/reviews/
  ▼
Django REST Framework   ←── thin HTTP boundary only
  │
  ▼
ReviewOrchestrationService  ←── calls LangGraph, not Django internals
  │
  ▼
LangGraph Workflow
  │
  ├── parse_diff      ←── deterministic, no LLM
  ├── build_context   ←── calls MCP client → MCP server
  ├── correctness_review  ←── LLM + structured output
  ├── validate_findings   ←── Pydantic schema gate
  └── END
        │
        ▼
   Finding[] (persisted via Django ORM)
        │
        ▼
   React UI (display + Accept/Dismiss → POST feedback)
```"""

new_arch = """## Architecture Overview

```mermaid
flowchart TD
    %% Node Styling
    classDef start_end fill:#f9f9f9,stroke:#333,stroke-width:2px,color:#333
    classDef deterministic fill:#e1f5fe,stroke:#0288d1,stroke-width:2px,color:#333
    classDef react_agent fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#333
    classDef data_flow fill:#fff3e0,stroke:#f57c00,stroke-width:1px,color:#333,stroke-dasharray: 5 5

    %% Graph Nodes
    START((START)):::start_end
    END_NODE((END)):::start_end

    subgraph Preparation Phase ["Phase 1: Preparation (Deterministic)"]
        ParseDiff[parse_diff<br/>Extract Hunks & Lines]:::deterministic
        
        subgraph BuildContext ["build_context"]
            Planner[Context Planner<br/>Risk Scoring & Decision]:::deterministic
            Partition[Partition Diff into<br/>Scoped Review Units]:::deterministic
        end
    end

    subgraph Specialist Phase ["Phase 2: Specialist Execution (Parallel)"]
        Correctness[correctness_review<br/>LangChain ReAct Agent]:::react_agent
        Security[security_review<br/>LangChain ReAct Agent]:::react_agent
        Linter[deterministic_checks<br/>Diff-Aware Ruff Linter]:::deterministic
    end

    subgraph Consolidation Phase ["Phase 3: Consolidation (Deterministic)"]
        Merge[merge_findings<br/>Deduplicate & Combine]:::deterministic
        Validate[validate_findings<br/>Zod Schema Gate]:::deterministic
    end

    %% Data Flow Nodes (Invisible logically, used for illustration)
    ReviewUnits(("[ReviewUnits & Decisions]")):::data_flow

    %% Edges
    START --> ParseDiff
    ParseDiff --> Planner
    Planner --> Partition
    Partition --> ReviewUnits
    
    ReviewUnits -->|Units categorized: correctness| Correctness
    ReviewUnits -->|Units categorized: security| Security
    ReviewUnits -->|Base vs Target refs| Linter
    
    Correctness --> Merge
    Security --> Merge
    Linter --> Merge
    
    Merge --> Validate
    Validate --> END_NODE

    %% Tool Loop Detail (Optional Callouts)
    Correctness -.->|read_file / find_references| MCP(MCP Server)
    Security -.->|read_file / find_references| MCP
```

### Context Engineering Components

To efficiently handle large diffs (e.g., 20k+ lines) without exceeding token limits or blowing up latency, the system relies on several advanced context engineering strategies:

1. **Deterministic Context Planner (`build_context` node)**: 
   Rather than blindly feeding the entire diff or pre-fetching massive amounts of surrounding code, the planner acts as a conservative heuristic engine. It evaluates the git diff for risk signals (`eval()`, `SQL`, `authorization` keywords, `open()`) and complexity. It decides whether the change can be evaluated on a fast-path (`sufficient_from_diff`), or if it requires cross-file MCP tool retrieval (`requires_cross_file_context`).

2. **Review-Unit Partitioning**:
   The monolithic git diff is split into file-scoped `ReviewUnit` payloads. The planner categorizes each unit (e.g., routing `auth.py` to the Security Agent, and `math.py` to the Correctness Agent). The downstream parallel agents receive **only** the units assigned to their specialty. This massively reduces token bloat (e.g., dropping a 300k token review down to 65k tokens).

3. **Diff-Aware Baseline Linter (`deterministic_checks` node)**:
   Instead of reporting all static analysis warnings in a file, the linter node runs `ruff` on the `base_ref` and `target_ref`, subtracting the baseline to report *only* strictly new findings introduced by the commit. This eliminates pre-existing technical debt noise.

4. **Lean ReAct Tool Loop (`correctness_review` / `security_review`)**:
   Instead of front-loading 20 lines of surrounding code and cross-file references into the initial prompt, the LangGraph agents are given the raw, scoped diff hunks. If the Context Planner marked the change as `requires_cross_file_context`, the LLM utilizes MCP tools (`read_file`, `find_references`) dynamically during the ReAct loop to fetch exactly what it needs, keeping the context window incredibly lean."""

if old_arch in content:
    content = content.replace(old_arch, new_arch)
else:
    print("Could not find the exact old architecture block.")

with open('DESIGN.md', 'w') as f:
    f.write(content)

