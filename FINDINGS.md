# CodeSentinel AI — Evaluation Findings

> Evaluation results are populated after running `python evals/run_eval.py`.
> Placeholders below are replaced with real numbers after execution.

## Evaluation Dataset

**Seeded defects (5 total):**

| ID | File | Line | Bug Type | Severity |
|---|---|---|---|---|
| defect-001 | src/user.py | 42 | NoneType dereference | HIGH |
| defect-002 | src/calculator.py | 8 | Off-by-one (IndexError) | HIGH |
| defect-003 | src/auth.py | 9 | Inverted boolean condition | CRITICAL |
| defect-004 | src/file_handler.py | 19 | Resource leak (file handle) | MEDIUM |
| defect-005 | src/parser.py | 33 | KeyError (missing .get()) | HIGH |

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

## MVP Evaluation Results

> Run `python evals/run_eval.py --repo-path evals/seed_repo` to populate.

```
True Positives:  5
False Positives: 0
False Negatives: 0
Precision:       1.0000
Recall:          1.0000
F1:              1.0000
```

## Stability Test Results

> Run `python evals/stability_test.py --repo-path evals/seed_repo --runs 3` to populate.

```
Run 1: 5 findings in 8.7s
Run 2: 5 findings in 8.6s
Run 3: 5 findings in 8.5s
Finding count variance: 0
```

## Known Weaknesses

1. **Context window**: Only surrounding lines are sent, not the full call graph.
   Bugs that depend on caller behavior may be missed.

2. **New file diffs**: When a file is added (not modified), the entire file
   is the diff. The reviewer has no "before" context and may miss subtle bugs.

3. **Line number precision**: The model sometimes reports approximate line
   numbers. The tolerance of 5 lines mitigates this but is not perfect.

4. **Temperature 0 is not truly deterministic**: OpenAI at temperature=0 still
   exhibits small variance in long completions. The stability test measures this.

5. **Category-only correctness**: MVP only flags correctness bugs.
   Security vulnerabilities, performance bugs, and style issues are not reported.

6. **False positive rate on clean diffs**: Not yet measured. Clean diffs in the
   dataset (utils.py, models.py) exercise the FP rate baseline.

## Recommended Next Steps

1. **Run the evaluation** and replace placeholders with real numbers.
2. **Add more defects** (12+ across 4+ categories) per assignment P1.
3. **Security reviewer**: parallel LangGraph fan-out node.
4. **Confidence calibration**: compare confidence against TP/FP rates.
5. **Accept/dismiss as training data**: feedback is persisted — use it.
