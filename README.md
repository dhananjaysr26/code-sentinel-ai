# CodeSentinel AI

AI-powered code review and evaluation platform. Reviews a Git diff and produces
structured correctness findings through a LangGraph orchestration pipeline.

## Architecture

```
User
  │
  ▼
React (TypeScript + Vite)          ← http://localhost:5173
  │  POST /api/reviews/
  ▼
Django REST Framework              ← http://localhost:8000
  │
  ▼
ReviewOrchestrator
  │
  ▼
LangGraph Workflow
  ├── parse_diff     (GitService + DiffParser — no LLM)
  ├── build_context  (MCP client → MCP server → repo)
  ├── correctness_review  (OpenAI structured output)
  └── validate_findings   (Pydantic schema gate)
        │
        ▼
   ReviewFinding[] → Django ORM → React UI
```

### MCP Data Path

```
LangGraph (build_context node)
  → StdioMCPClient
    → MCP server (mcp_server/server.py, stdio transport)
      → Git CLI / filesystem (local repository)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 4.2 + DRF |
| Agent | LangGraph 0.2 |
| LLM | OpenAI (gpt-4o, configurable) |
| Tool protocol | MCP (stdio) |
| Validation | Pydantic v2 |
| Frontend | React 18 + TypeScript + Vite |
| Server state | @tanstack/react-query |
| Database | SQLite |
| Package mgmt | pip + venv (backend), pnpm (frontend) |

## Observability & LLM Usage Tracking

CodeSentinel AI tracks and persists detailed operational metrics for all LLM calls:
- **Tokens:** Input (prompt), Output (completion), and Total tokens.
- **Latency:** Measured application-side for accurate end-to-end timing.
- **Estimated Cost:** Automatically computed using a centralized pricing table.
- **Reviewer Usage:** Detailed metrics per reviewer (e.g. Correctness, Security) allowing analysis of parallel execution performance.

### Supported Providers
- **Amazon Bedrock:** Analyzes the provider's `amazon-bedrock-invocationMetrics` metadata.
- **OpenAI:** Uses standard `usage_metadata` extracted from the structured LLM response.

### Pricing Configuration
Pricing is configured in `backend/sentinel/services/pricing.py`. To add a new model, simply add its input and output prices per 1M tokens to the `MODEL_PRICING` dictionary. If a model's pricing is missing, the application will gracefully return `null` for the estimated cost, and the UI will display "N/A" without breaking the review flow.

## Prerequisites

- Python 3.11+
- Node.js 18+ and pnpm
- git
- An OpenAI API key

## Installation

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend

```bash
cd frontend
pnpm install
```

## Environment Variables

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set:
#   OPENAI_API_KEY=sk-...
#   DJANGO_SECRET_KEY=...
#   MCP_SERVER_SCRIPT=/absolute/path/to/mcp_server/server.py
```

## Running

### Step 1: Start MCP Server (test it)
```bash
# The MCP server is launched automatically by the Django app for each review.
# To test it standalone:
python mcp_server/server.py
```
> The MCP server runs as a subprocess — you don't need to keep it running manually.

### Step 2: Start Django

```bash
cd backend
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

### Step 3: Start React

```bash
cd frontend
pnpm dev
```

Open http://localhost:5173

## Example Review Request

```bash
curl -X POST http://localhost:8000/api/reviews/ \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/absolute/path/to/evals/seed_repo",
    "base_ref": "HEAD~1",
    "target_ref": "HEAD"
  }'
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/reviews/ | Trigger a review |
| GET | /api/reviews/{id}/ | Get review + findings |
| POST | /api/reviews/{id}/findings/{fid}/feedback/ | Accept or dismiss |

## Running the Evaluation

CodeSentinel AI provides two ways to evaluate the system against our seeded repositories: via the **Web UI** or via the **Terminal**.

### Option 1: Testing from the Web UI

1. Start both the Django backend and the React frontend (see the "Running" section above).
2. Open the UI at `http://localhost:5173`.
3. Click **"New Review"**.
4. Enter the absolute path to one of the test repositories (e.g., `/absolute/path/to/test-repo/breakableflask`).
5. Set the Base to the previous commit (e.g., `HEAD~1` or `b3297f7~1`) and Target to the vulnerable commit (e.g., `HEAD` or `b3297f7`).
6. Click Submit. The LangGraph orchestration will run in real-time, executing MCP tool calls in the background, and will render the findings natively in the UI with severity badges and linter filtering options.

### Option 2: Testing from the Terminal (`evaluate.py`)

For automated, headless stability testing across multiple runs, use the unified `evaluate.py` script. 
Make sure your virtual environment is active first:
```bash
cd backend
source .venv/bin/activate
cd ..
```

**Evaluate a specific repository (e.g., single-js):**
```bash
python evaluate.py \
  --repo /Users/dhananjaysingh/uncoders/AI_APP/code-sentinel-ai/test-repo/single-js \
  --base HEAD~1 \
  --target HEAD \
  --runs 3 \
  --provider openai
```

**Commands for all 5 test repositories:**

1. **auth-bypass**
```bash
python evaluate.py --repo $(pwd)/test-repo/auth-bypass --base HEAD~1 --target HEAD --runs 3
```

2. **multi-loop**
```bash
python evaluate.py --repo $(pwd)/test-repo/multi-loop --base HEAD~1 --target HEAD --runs 3
```

3. **seed_repo**
```bash
python evaluate.py --repo $(pwd)/test-repo/seed_repo --base HEAD~1 --target HEAD --runs 3
```

4. **single-js**
```bash
python evaluate.py --repo $(pwd)/test-repo/single-js --base HEAD~1 --target HEAD --runs 3
```

5. **breakableflask**
```bash
python evaluate.py --repo $(pwd)/test-repo/breakableflask --base b3297f7~1 --target b3297f7 --runs 3
```

**Evaluate ALL 5 repositories automatically in a single command:**
```bash
python evaluate.py --all --runs 3
```
This will iterate through the entire suite, run the evaluation 3 times per repository, and output aggregated token usage, latency, and standard deviation metrics for finding stability.

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

## Project Structure

```
code-sentinel-ai/
├── backend/
│   ├── config/           Django settings, urls, wsgi
│   ├── apps/reviews/     Django models, serializers, views, urls
│   ├── sentinel/
│   │   ├── graph/        LangGraph workflow, state, nodes
│   │   ├── context/      ContextBuilder
│   │   ├── mcp/          MCP client interface
│   │   ├── schemas/      Pydantic schemas (findings, diff, context)
│   │   └── services/     GitService, DiffParser, Deduplicator, Orchestrator
│   └── tests/            Unit + integration tests
├── mcp_server/           MCP server (get_diff, read_file tools)
├── frontend/             React + TypeScript UI
├── evals/
│   ├── fixtures/         Ground truth defects + clean diffs
│   ├── seed_repo/        Pre-initialized git repo with seeded bugs
│   ├── metrics.py        Precision/recall calculation
│   ├── run_eval.py       Evaluation runner
│   └── stability_test.py Stability (nondeterminism) test
├── DESIGN.md             Architecture decisions
├── FINDINGS.md           Evaluation results and limitations
└── README.md             This file
```

## MCP Tools
CodeSentinel uses the Model Context Protocol to access the local repository safely.
The MCP server exposes the following tools:
- `get_diff(repo_path, base_ref, target_ref)`: Gets the unified diff.
- `read_file(repo_path, file_path, start_line, end_line)`: Reads lines from a file.
- `find_references(repo_path, symbol, [path])`: Deterministically finds usages, calls, and imports of a symbol in the Python codebase using AST analysis.
- `run_linter(repo_path, path)`: Executes a static analysis tool (`ruff`) on the specified Python file and returns structured issues.

### Example MCP Calls
```json
// find_references
{
  "symbol": "process_payment",
  "references": [
    {"file": "src/checkout.py", "line": 45, "column": 12, "kind": "call"}
  ],
  "count": 1
}

// run_linter
{
  "path": "src/db.py",
  "success": true,
  "issues": [
    {"line": 34, "column": 12, "code": "E501", "severity": "warning", "message": "Line too long"}
  ],
  "issue_count": 1,
  "tool": "ruff"
}
```

### Advanced Context Engineering
CodeSentinel AI leverages a 3-Layer Selective Context architecture to minimize input token explosion during deep multi-hop reasoning. Instead of blindly sending full file transcripts on every loop, the agent normalizes retrieved files into an `evidence_store` and injects a heavily compressed Context Manifest into the prompt. This keeps context windows small, latency low, and drastically reduces token costs while maintaining high recall.
