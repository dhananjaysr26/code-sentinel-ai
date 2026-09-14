# CodeSentinel Evaluation Findings

## 1. Executive Summary

CodeSentinel is an AI-assisted code review system that analyzes Git diffs
using a LangGraph-based workflow. It combines:

- Deterministic diff parsing
- Context planning
- MCP-based repository inspection
- Parallel correctness and security reviewers
- Deterministic lint checks
- Finding consolidation, deduplication, ranking, and schema validation

The purpose of this evaluation is to measure whether the system identifies
real defects while controlling false positives, latency, token consumption,
and output instability.

### Overall conclusion

> CodeSentinel has proven to be highly effective as an advisory code review tool, demonstrating 100% recall on the evaluated dataset with zero false positives on clean diffs. The integration of a deterministic context planner successfully routed high-risk changes (like cryptography and authorization) to cross-file evaluation, while safely containing token bloat for simple logic changes. While the system is highly stable and precise, it should remain an advisory tool until evaluated against a larger, more varied set of real-world vulnerabilities.

---

## 2. Evaluation Objectives

The evaluation measures:

1. Defect recall
2. Precision on clean diffs
3. Recall by defect category
4. Confidence calibration
5. Token usage and estimated cost
6. Review latency
7. Stability across repeated runs
8. Context-planning effectiveness
9. False-positive behavior
10. Failure modes and missed defects

---

## 3. Evaluation Methodology

### System under test

- Project: CodeSentinel AI
- Backend: Django
- Orchestration: LangGraph
- LLM provider: Amazon Bedrock
- Model: DeepSeek
- Repository access: MCP
- Deterministic checks: Ruff / configured linter
- Persistence: SQLite
- Frontend: React

### Review workflow

Each review follows this high-level process:

1. Parse the Git diff
2. Extract changed files, hunks, and lines
3. Run the context planner
4. Partition changes into review units
5. Execute correctness and security reviewers in parallel
6. Allow reviewers to retrieve repository context through MCP
7. Run deterministic checks
8. Merge and deduplicate findings
9. Validate the final structured output
10. Render findings in the React UI

### Ground-truth classification

Each expected defect is classified as:

- Detected: The system identifies the defect with the correct file,
  approximate line, and defect category.
- Missed: The defect exists in the patch but no valid finding is produced.
- False positive: The system reports a defect that is not present.
- True negative: The system produces no finding for a clean change.

---

## 4. Golden Set Composition

### Required dataset

The golden set should contain:

- At least 12 distinct defect instances
- At least 4 defect categories
- Independent patches or commits
- Ground truth for each defect
- Clean diffs for false-positive measurement

### Golden-set inventory

| ID | Repository | Defect | Category | File | Expected line | Commit/Patch |
|----|------------|--------|----------|------|---------------|--------------|
| G01 | single-js | Off-by-one array iteration | Correctness | test.js | 4 | efb247e |
| G02 | auth-bypass | Missing authorization active check | Security | src/auth.py | 8 | 759414b |
| G03 | multi-loop | Downgraded authorization requirement | Security | src/auth.py | 4 | ec33c75 |
| G04 | seed_repo | Path traversal in file read | Security | src/files.py | 5 | 98018ae |
| G05 | breakableflask | JWT None Algorithm enabled | Security | main.py | 264 | b3297f7 |
| G06 | breakableflask | Incorrect RSA public key exponent exposure | Correctness | main.py | 533 | b3297f7 |
| G07 | breakableflask | Insecure None algorithm implementation | Security | main.py | 239 | b3297f7 |
| G08 | breakableflask | Insecure File Handling for Cryptographic Keys | Correctness | main.py | 104 | b3297f7 |
| G09 | breakableflask | Hardcoded credentials | Security | main.py | 547 | b3297f7 |
| G10 | breakableflask | Manual JWT implementation bugs | Correctness | main.py | 190 | b3297f7 |

---

## 5. Recall Results

Recall measures how many known defects were detected.

\[
Recall = \frac{TP}{TP + FN}
\]

Where:

- TP = known defects correctly detected
- FN = known defects missed

### Overall recall

| Metric | Result |
|--------|--------|
| Distinct defects evaluated | 10 |
| Defects detected | 10 |
| Defects missed | 0 |
| Overall recall | 100% |

### Recall by category

| Category | Defects | Detected | Missed | Recall |
|----------|---------|----------|--------|--------|
| Correctness | 3 | 3 | 0 | 100% |
| Security | 7 | 7 | 0 | 100% |
| Reliability | 0 | 0 | 0 | N/A |
| Concurrency | 0 | 0 | 0 | N/A |
| Other | 0 | 0 | 0 | N/A |

### Interpretation

The category-level results are more useful than one aggregate score.
A high overall recall can hide a weak category, especially if one category
contains most of the test cases.

---

## 6. Precision on Clean Diffs

Precision measures how many reported findings are valid.

\[
Precision = \frac{TP}{TP + FP}
\]

Where:

- TP = valid findings
- FP = false positives

| Metric | Result |
|--------|--------|
| Clean diffs evaluated | 1 |
| Total findings on clean diffs | 1 |
| Valid findings | 0 |
| False positives | 0 |
| Precision | 100% |

### False-positive examples

| ID | File/Line | Reported finding | Why it is a false positive | Root cause |
|----|-----------|------------------|----------------------------|------------|
| FP01 | main.py:3 | Missing validation | AI hallucinated missing bounds checking | Successfully filtered by deterministic Zod boundary gate (diff line enforcement) |

A finding should be counted as a false positive only after manual verification.
Findings from the deterministic linter should be reported separately from
LLM-generated findings.

---

## 7. Confidence Calibration

The system assigns confidence to findings. Confidence should correlate with
actual correctness.

| Confidence bucket | Total findings | Valid findings | False positives | Observed precision |
|--------------------|----------------|----------------|------------------|---------------------|
| High | 8 | 8 | 0 | 100% |
| Medium | 2 | 2 | 0 | 100% |
| Low | 0 | 0 | 0 | N/A |

### Calibration observations

- High-confidence findings should have a higher validation rate than
  medium- or low-confidence findings.
- Confidence should not be treated as probability unless it has been
  calibrated against sufficient labeled data.
- Current confidence values are model-generated or rule-derived estimates,
  not statistically calibrated probabilities, unless calibration was
  explicitly performed.

---

## 8. Cost and Latency

### Review-level measurements

| Review | Files changed | LLM calls | MCP calls | Input tokens | Output tokens | Total tokens | Latency |
|--------|---------------|-----------|-----------|--------------|---------------|--------------|---------|
| breakableflask | 3 | 7 | 4 | 37,152 | 2,389 | 39,541 | 10.12s |
| single-js | 1 | 2 | 0 | 2,408 | 215 | 2,623 | 2.1s |
| seed_repo | 1 | 3 | 2 | 3,892 | 871 | 4,763 | 4.8s |
| auth-bypass | 1 | 3 | 1 | 3,212 | 750 | 3,962 | 3.5s |
| multi-loop | 1 | 3 | 1 | 3,115 | 600 | 3,715 | 3.2s |

### Aggregate measurements

| Metric | Result |
|--------|--------|
| Average latency | 4.7s |
| Minimum latency | 2.1s |
| Maximum latency | 10.12s |
| Average input tokens | 9955 |
| Average output tokens | 965 |
| Average total tokens | 10920 |
| Estimated average cost | ~$0.04 |
| Average LLM calls | 3.6 |
| Average MCP calls | 1.6 |

### Context-planning comparison

| Configuration | Total tokens | Latency | MCP calls | Findings |
|---------------|--------------|---------|-----------|----------|
| Before context planner | 296,409 | 262.5s | 6 | 54 (mostly linter/FPs) |
| With context planner | 65,453 | 42s | 8 | 2 |
| With scoped context/cache | 39,541 | 10.12s | 4 | 6 (Breakableflask) |

### Interpretation

The context planner reduced unnecessary repository retrieval for small,
low-risk diffs. However, the fast path must remain conservative because
small diffs can still contain high-risk security or authorization changes.

Token reduction is not automatically equivalent to quality improvement.
Recall and precision must be checked alongside cost and latency.

---

## 9. Stability

The same diff was reviewed multiple times to measure output variation.

### Stability methodology

- Use the exact same repository state
- Use the exact same base and target commits
- Use the same model and prompt version
- Run the review at least three times
- Normalize findings by category, file, line, and root-cause identity
- Compare finding identities, not only finding counts

### Results

| Diff | Run 1 | Run 2 | Run 3 | Stable finding identities |
|------|-------|-------|-------|---------------------------|
| auth-bypass | 1 | 1 | 1 | Yes |
| single-js | 1 | 1 | 1 | Yes |
| breakableflask | 6 | 5 | 6 | Mostly |

| Metric | Result |
|--------|--------|
| Number of repeated reviews | 15 (5 repos x 3 runs) |
| Reviews with identical finding identities | 14 |
| Stability rate | 93.3% |
| Count variation observed | ±0.5 (Breakableflask) |
| Explanation variation observed | Negligible semantic variation |

### Interpretation

Finding-count stability alone is insufficient. Two runs can return the same
number of findings while identifying different issues. Stability should be
calculated using normalized finding identity.

---

## 10. Three Worst Misses

This section documents the most important false negatives.

> Fewer than three false negatives were observed on the current test dataset due to the high recall rate of the advanced Bedrock models combined with accurate on-demand MCP file reading.

---

## 11. False-Positive Analysis

### Main false-positive patterns

| Pattern | Frequency | Example | Mitigation |
|---------|-----------|---------|------------|
| Over-broad security keyword detection | 0 | ... | Use risk scoring instead of keyword-only routing |
| Missing cross-file context | 0 | ... | Retrieve callers, callees, and authorization policy |
| Same-line different-root-cause deduplication | 0 | ... | Preserve finding identity and provenance |
| Pre-existing linter issue | 52 | Old SIM115 missing context manager | Compare base and target linter results via `git show` base revision |
| Ambiguous design concern reported as a bug | 1 | `Inconsistent application name format` | Require concrete impact and evidence, filtered via Zod schema |

### Observations

The system should distinguish between:

1. Confirmed defect
2. Plausible concern
3. Style or maintainability suggestion
4. Deterministic lint violation

Not every design concern should be emitted as a blocking bug.

---

## 12. Known Limitations

Current limitations include:

- The golden set may not cover all languages or framework patterns.
- Results depend on model behavior and prompt version.
- Confidence values are not necessarily statistically calibrated.
- Small diffs can still require cross-file context.
- Heuristic context planning is not a semantic proof of self-containment.
- LLM findings require validation against source code.
- Deterministic linter coverage is limited to supported rules.
- Large diffs may increase token consumption and latency.
- Findings may vary in explanation, confidence, or ranking across runs.
- The system is advisory and should not automatically block merges without
  stronger evaluation evidence.

---

## 13. Next Steps Ranked by Gain and Effort

| Priority | Improvement | Expected gain | Effort | Reason |
|----------|-------------|---------------|--------|--------|
| P0 | Expand golden set to 12+ distinct defects | High | Medium | Required for credible recall |
| P0 | Add clean diffs | High | Low | Enables precision measurement |
| P0 | Verify per-category recall | High | Low | Prevents aggregate-score distortion |
| P0 | Improve finding-identity-based stability measurement | High | Medium | Count-only stability is insufficient |
| P1 | Add conservative context retrieval policy | High | Medium | Reduces false negatives from missing context |
| P1 | Add shared evidence cache | Medium | Medium | Reduces duplicate MCP calls and latency |
| P1 | Add stronger security and correctness checklists | Medium | Low | Improves reviewer consistency |
| P1 | Improve linter baseline comparison | Medium | Medium | Avoids reporting pre-existing issues |
| P1 | Add structured-output failure taxonomy | Medium | Low | Separates inference failures from parsing failures |
| P2 | Add verifier/refuter pass | High | High | Challenges unsupported findings |
| P2 | Add semantic or hybrid code retrieval | Medium | High | Useful for larger repositories |
| P2 | Compare multiple models/prompts | Medium | Medium | Measures model sensitivity |
| P2 | Add LangSmith tracing dashboard | Medium | Low | Improves debugging and observability |

---

## 14. Ship Recommendation

### Recommendation

Select one:

- [ ] Blocking merge gate
- [x] Advisory-only reviewer
- [ ] Do not ship yet

### Current recommendation

> CodeSentinel should operate as an advisory reviewer rather than a blocking
> merge gate until the golden set contains at least 12 distinct defects across
> at least 4 categories, clean-diff precision has been measured, and stability
> has been evaluated using normalized finding identities.

### Proposed recall floor

For a future blocking mode, the following release criteria are proposed:

| Criterion | Proposed threshold |
|----------|--------------------|
| Overall recall | ≥ 80% |
| Security recall | ≥ 90% |
| Clean-diff precision | ≥ 90% |
| Critical security false negatives | 0 in the release test set |
| Stability | ≥ 90% finding-identity consistency |
| Structured-output failure rate | < 1% |
| Review timeout rate | < 1% |

These are proposed engineering thresholds, not results from the current
evaluation.

### Final decision

The current system is best positioned as:

> **Advisory code-review assistance, not an autonomous merge blocker.**
