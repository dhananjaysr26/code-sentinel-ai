# CodeSentinel AI — Architecture & Design

## Purpose

CodeSentinel AI is an AI-powered code review platform that accepts a local Git
repository and a revision range, runs a structured correctness analysis through
a LangGraph agent, and returns machine-readable findings. The MVP implements a
single vertical slice from Git diff to UI feedback.

---

## Architecture Overview

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
```

### MCP Data Path

```
LangGraph (build_context node)
  │
  ▼
MCPClient (stdio transport)
  │  calls tools: get_diff, read_file
  ▼
MCPServer (mcp_server/server.py)
  │
  ▼
Git CLI / filesystem (local repository)
```

---

## Technology Decisions

| Concern | Choice | Reason |
|---|---|---|
| Backend | Django + DRF | Required by assignment |
| Agent | LangGraph | Required; enables node-level testing |
| LLM | OpenAI (configurable) | Required |
| Tool protocol | MCP (stdio) | Required; explicit boundary |
| DB | SQLite | No external services needed for MVP |
| Frontend | React + TypeScript + Vite | Fast local dev, typed |
| State mgmt | React Query (server state) | Simplest correct choice |
| Validation | Pydantic v2 | Required |
| Package mgmt | pip + pyproject.toml (backend), pnpm (frontend) | Reproducible |

---

## Why LangGraph (not raw LLM calls)

1. Explicit node boundaries → each node is independently testable
2. Typed shared state → no implicit data passing
3. Graph topology visible in code → defensible in review
4. Future fan-out (parallel specialist reviewers) fits naturally
5. Error isolation: one failing node does not crash the whole run

## Why MCP (not direct function calls)

1. Assignment requirement — demonstrates understanding of tool protocols
2. Clean interface boundary: the agent cannot call internal functions directly
3. MCP server can later be replaced or extended without changing the agent
4. Demonstrates the correct architecture: agent ↔ tool server ↔ repository

---

## LangGraph State

```python
class ReviewState(TypedDict):
    # Input
    repo_path: str
    base_ref: str
    target_ref: str
    # Populated by parse_diff
    raw_diff: str
    changed_files: list[ChangedFile]
    diff_hunks: list[DiffHunk]
    # Populated by build_context
    context_blocks: list[ContextBlock]
    # Populated by correctness_review
    raw_findings: list[dict]
    # Populated by validate_findings
    findings: list[Finding]
    # Bookkeeping
    errors: list[str]
    metadata: dict
```

State is intentionally flat. Future reviewers append to `raw_findings`.

---

## LangGraph Nodes

| Node | Input fields | Output fields | LLM? |
|---|---|---|---|
| `parse_diff` | repo_path, base_ref, target_ref | raw_diff, changed_files, diff_hunks | No |
| `build_context` | changed_files, diff_hunks | context_blocks | No (MCP calls) |
| `correctness_review` | diff_hunks, context_blocks | raw_findings | Yes |
| `validate_findings` | raw_findings | findings, errors | No |

---

## Context Strategy (MVP)

For each hunk in the diff:
1. Call `read_file(path, line_range)` via MCP to get N lines before and after the hunk.
2. Default window: 20 lines before hunk start, 20 lines after hunk end.
3. Attach the raw hunk diff.
4. Resulting `ContextBlock` contains: file, line_range, surrounding_code, hunk_diff.

**Token budget**: A `ContextBudget` dataclass (max_tokens, per_file_limit) is
passed through the graph. The MVP policy is a simple truncation: if accumulated
context exceeds `max_tokens`, trim older/smaller hunks first.

This is documented here so the future prioritization logic (ranked by change
size, recency, call-graph distance) has an obvious home.

---

## Finding Schema

```python
class Severity(str, Enum): LOW / MEDIUM / HIGH / CRITICAL
class Category(str, Enum): CORRECTNESS (MVP only)
class Source(str, Enum):   LLM / LINTER / AST

class Finding(BaseModel):
    id: str                   # UUID
    file: str
    line: int | None
    title: str
    category: Category
    severity: Severity
    confidence: float         # 0.0 – 1.0
    explanation: str
    evidence: str
    suggested_fix: str | None
    source: Source
```

The schema is intentionally minimal. Future sources (linter, security) are
already enumerated in `Source` and `Category`.

---

## API Boundary

Django views do ONE thing: accept HTTP, validate request schema, delegate to
`ReviewOrchestrationService`, return serialized response. No LangGraph code
lives in views.py.

Endpoints:
- `POST /api/reviews/`
- `GET /api/reviews/{id}/`
- `POST /api/reviews/{id}/findings/{finding_id}/feedback/`

---

## Deduplication (MVP)

`FindingDeduplicator.deduplicate(findings: list[Finding]) -> list[Finding]`

MVP policy: deduplicate on `(file, line, title)` hash, keeping the finding with
the highest confidence. This interface is the extension point for future
semantic deduplication across reviewers.

---

## Evaluation

5 seeded defects + 2 clean diffs.

Ground truth is stored as JSON in `evals/fixtures/`.

Matching: a prediction matches a ground truth if:
- same file path (exact)
- `abs(predicted_line - expected_line) <= 5` (line proximity)
- category matches

Limitations of this matching: line proximity can produce false matches for
dense bugs; category matching requires the reviewer to output the correct enum.
Both are documented in FINDINGS.md.

---

## What Was Intentionally NOT Built

- GitHub URL cloning
- Authentication / OAuth
- Celery / Redis / message queues
- PostgreSQL (SQLite is sufficient)
- Kubernetes / Docker Compose (beyond local dev)
- Security reviewer (P1)
- Parallel fan-out (P1)
- LangSmith / tracing (P2)
- Cost dashboard (P2)

These are enumerated here so the absence is deliberate, not an oversight.

---

## Future Evolution (P1)

```
START
  ├── parse_diff
  ├── build_context
  ├── correctness_review ──┐
  ├── security_review    ──┤  (parallel fan-out)
  ├── linter_review      ──┘
  ├── deduplicate_findings
  ├── validate_findings
  └── END
```

The current graph topology makes this a straightforward extension.
