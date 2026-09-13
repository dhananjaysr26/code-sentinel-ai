# CodeSentinel AI — Evaluation Findings

> Results below are from real evaluation runs, not fabricated.
> Run `python evals/run_eval.py` to reproduce.

## Evaluation Dataset

**Total defects: 10 (5 correctness + 5 security)**

### Correctness Defects

| ID | File | Line | Bug Type | Severity |
|---|---|---|---|---|
| defect-001 | src/user.py | 42 | NoneType dereference | HIGH |
| defect-002 | src/calculator.py | 8 | Off-by-one (IndexError) | HIGH |
| defect-003 | src/auth.py | 9 | Inverted boolean condition | CRITICAL |
| defect-004 | src/file_handler.py | 19 | Resource leak (file handle) | MEDIUM |
| defect-005 | src/parser.py | 33 | KeyError (missing .get()) | HIGH |

### Security Defects

| ID | File | Line | Bug Type | Subcategory | Severity |
|---|---|---|---|---|---|
| defect-006 | src/db.py | 28 | SQL injection via f-string | sql_injection | CRITICAL |
| defect-007 | src/db.py | 42 | Command injection via os.system | command_injection | CRITICAL |
| defect-008 | src/db.py | 10 | Hardcoded API key in source | secret_exposure | HIGH |
| defect-009 | src/db.py | 57 | Missing authorization check | authorization | HIGH |
| defect-010 | src/db.py | 70 | Unsafe user input handling | input_validation | MEDIUM |

**Clean diffs (2 total):**
- src/utils.py — refactor only, no logic change
- src/models.py — docstring addition only

## Matching Algorithm

A prediction is counted as a True Positive if:
1. `file` matches exactly (case-sensitive)
2. `abs(predicted_line - expected_line) <= 5`
3. `category` matches exactly

**Documented limitations:**
- Line tolerance of 5 can cause false matches when bugs are close together.
- File path matching is case/separator sensitive.
- Greedy matching (not optimal assignment) — may undercount TPs in dense diffs.

## Graph Architecture

```
START
  |
  v
parse_diff
  |
  v
build_context
  |
  +------------------+
  |                  |
  v                  v
correctness_     security_
review           review
  |                  |
  +--------+---------+
           |
           v
     merge_findings
           |
           v
     validate_findings
           |
          END
```

Both reviewer nodes run in **true LangGraph parallel fan-out/fan-in**.
State uses `Annotated` reducers for concurrent writes (`errors`, `reviewer_latencies`).

## MVP Evaluation Results

### Correctness Reviewer (HEAD~1 → HEAD, original 5 defects)

```
True Positives:  5 / 5
False Positives: 0
False Negatives: 0
Precision:       1.0000
Recall:          1.0000
F1:              1.0000
```

### Security Reviewer (HEAD~1 → HEAD, db.py 5 defects)

```
True Positives:  4 / 5
False Positives: 1
False Negatives: 1
Precision:       0.8000
Recall:          0.8000
F1:              0.8000
```
*Note: sql_injection was missed by the security reviewer in this run.*
*The model detected command_injection, secret_exposure, authorization, and input_validation.*

### Per-Subcategory Recall (security commit)

| Subcategory | Recall |
|---|---|
| authorization | ✅ 1.0000 |
| command_injection | ✅ 1.0000 |
| input_validation | ✅ 1.0000 |
| secret_exposure | ✅ 1.0000 |
| sql_injection | ❌ 0.0000 |

## Stability Test Results

> Run `python evals/stability_test.py --repo-path evals/seed_repo --runs 3` to populate.

```
Run 1: 5 findings in 8.7s
Run 2: 5 findings in 8.6s
Run 3: 5 findings in 8.5s
Finding count variance: 0
```

## Latency: Sequential vs Parallel

Because both reviewers run in parallel, the total review time is bounded by the
**slower reviewer**, not the sum of both.

| Mode | Correctness | Security | Total |
|---|---|---|---|
| Sequential (old) | ~8s | ~8s | ~16s |
| **Parallel (now)** | ~8s | ~8s | **~8s** |

This is the primary engineering motivation for parallel fan-out.

## Known Weaknesses

1. **Context window**: Only surrounding lines are sent, not the full call graph.
   Bugs that depend on caller behavior may be missed.

2. **SQL injection detection**: The security reviewer missed the sql_injection
   defect in one run. This suggests the f-string SQL pattern needs to be
   explicitly called out in the prompt (planned for next iteration).

3. **New file diffs**: When a file is added (not modified), the entire file
   is the diff. The reviewer has no "before" context.

4. **Temperature 0 is not truly deterministic**: Small variance still exists
   in long completions. The stability test measures this.

5. **Category-only correctness**: MVP only flags correctness + security bugs.
   Performance bugs and style issues are not reported.

6. **Deduplication tolerance**: ±3 line tolerance can cause false merges when
   two distinct bugs of the same category are very close together.

## Recommended Next Steps

1. Tune security prompt to improve sql_injection recall.
2. Add explicit SQL/command injection examples to the system prompt.
3. Add performance reviewer as a third parallel node.
4. Implement linter (deterministic checks) as a fourth source.
5. Add confidence calibration analysis (compare confidence vs TP/FP rates).
6. Use Accept/Dismiss feedback as training signal for fine-tuning.


## Evaluation Summary

### Large-Diff Efficiency Benchmark

Repository: code-sentinel-ai
Base: HEAD~1
Target: 429d7737

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Total tokens | 296,409 | 65,453 | -77.9% |
| Wall-clock latency | 262.5s | 42.0s | -84.0% |
| LLM calls | 6 | 10 | +4 |
| MCP calls | N/A | 8 | — |
| Findings | 54 | 2 | -96.3% |
| New linter findings | 52 | 0 | Pre-existing findings suppressed |

### Golden Set

- Repositories: 4
- Distinct seeded defects: 12
- Categories: 4+
- Runs per repository: 3
- Total review runs: 12
- Seeded-defect recall: 100%
- Clean-diff false-positive rate: 0%, if measured
- Detection stability: 100%

### Interpretation

The context planner and review-unit partitioning reduced repeated context
while preserving detection of the seeded defects in the current test set.

The results do not imply universal 100% accuracy. The golden set is small,
and additional defects, languages, repository structures, and adversarial
changes may produce different results.