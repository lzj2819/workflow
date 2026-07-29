# Day 3 Gate Status — dual-track calibration

## Decision

**GO for Day 4 implementation work.** This is only a Day 3 calibration Gate;
it is not a claim of a production end-to-end run, a C0--C5 experiment result,
or a completed multi-leaf workflow.

## S1 coding-positive track

| Evidence category | Result | Evidence |
|---|---|---|
| Fresh input provenance | PASS | Independent in-memory `POST /notes` task; no Tutor source/code/test reuse. |
| Strict execution completeness | PASS | `strict-run-20260729-j`: 4 component calls and 3 validator calls completed. |
| Strict semantic result | PASS | Strict audit PASS; final Mocktest PASS; 0 architecture defects; 0 uncovered requirements. |
| Independent Leaf decision | STOP_LAYERING | `leaf-run-20260729-b/leaf_gate_decision.json`, SHA-256 `0f3ecb24d01bf2da6a70fba1590e8e3102cd8c406df84275a65f04b78fbb9119`. Its formal inputs are a documented Leaf 1.0 adapter, not a change to the shared v0.2 Contract. |
| Real Coding Executor | PASS | One real local Codex CLI invocation (`gpt-5.6-terra`), isolated workspace, public specification and public tests only, 0 repairs needed. |
| Code verification | PASS | Public ASGI pytest: 2 passed. Generated `main.py` SHA-256 `0815d91447a63f9a53b3df7465c0d9c472bf88c26fef5dcf5cfde34bffde5434`. v0.2 result envelope schema validation and self-hash both passed. |

Retained local raw evidence (not committed because it contains machine absolute
paths): `vibe coding/experiments/day3-s1-positive/strict-run-20260729-j/` and
`vibe coding/experiments/day3-s1-positive/coding-run-20260729-a/`.

## CMP validation-negative track

| Evidence category | Result | Evidence |
|---|---|---|
| Source scope | Historical Tutor migration fixture only | It is a negative control and is not C0--C5 data. |
| Strict execution completeness | PASS | `strict-run-20260729-b`: 5 component calls and 5 validator calls completed; strict audit PASS. |
| Strict semantic result | FAIL | 5/5 scenarios failed; 17 findings, including missing interface, missing/invalid required fields, unsupported scenario flow, and orphan components. |
| Tool/environment result | No tool ERROR | Formal Mocktest report has `execution_status=COMPLETED`, `validation_status=FAIL`, and `TOOL_EXECUTION_ERROR=0`. |
| Downstream disposition | BLOCKED | CMP did not enter Leaf Gate or Coding Executor. |

The historical Feature is intentionally not repaired: it lacks concrete
input/response assertions. `experiments/day3-cmp-negative/input/cmp-current-layer.md`
is a read-only machine-parseable projection of the historical contracts used
only to permit complete strict execution. CMP formal report SHA-256:
`25bbe65d70fac7bd3b0774b7f54e84ec25e74370369e8168edb89cb5aa3fbec5`.

## Known boundary and next step

Leaf Gate formal mode requires schema version `1.0`, while the shared
VeriLayer Artifact Contract remains v0.2. Day 3 uses a documented derived
adapter; no shared Contract, main branch, or remote PR was modified.

Day 4 may start the fresh recursive root/child implementation. It must use a
new task and must not reuse S1 generated code or permit CMP to enter Coding.
