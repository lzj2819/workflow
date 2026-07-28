# B Day 2 Adapter draft and contract-change log

Status: blocked pending A's `verilayer/a-contract-integration` branch and an approved contract version. This is test design/pseudocode only, not an implementation or production evidence.

## PR handoff

Source branch: `verilayer/b-generation` at `cbe5b2c`.

Requested PR base: `verilayer/a-contract-integration`. On 2026-07-28 the remote branch was absent, so GitHub cannot create this PR with the required base. Do not retarget to `main`.

## Pending A decisions

1. Architecture and Testcases machine-readable artifact profiles and schemas.
2. Canonical bytes rule for `content_sha256`, including whether the field is excluded from the bytes it hashes.
3. Root/Child PRD envelope profile and repository-relative `content_path` rule.
4. The `run_id`, `project_id`, and `node_id` propagation/inheritance rules.
5. Formal PASS, FAIL, and ERROR semantics plus error object schema.

## Local draft algorithm

1. Validate the PRD envelope against A's frozen profile; unknown status, absolute path, missing identity, or legacy `child_node_id` produces a legal `ERROR` envelope.
2. Invoke only a configured executor. If absent, return `ERROR/error.category=EXECUTOR_NOT_CONFIGURED`; if a required validator dependency is absent, return `DEPENDENCY_MISSING`.
3. For successful execution, parse the JSON source of truth, verify required requirement traces and repository-relative paths, then recompute hashes using A's canonical bytes rule.
4. Preserve input `run_id`, `project_id`, and `node_id`; output no `child_node_id`.
5. For Gherkin, run `validate_feature.mjs` and `validate_requirement_graph.mjs`; persist command, exit code, stdout/stderr hashes, and error classification in the module result.

## Test status

`tests/integration/test_architecture_adapter.py` and `tests/integration/test_gherkin_adapter.py` are strict xfail contract tests. They must be unmarked and pass only after A freezes the pending items and B supplies the minimal Adapter implementation. Their deterministic test double is never a production executor or experiment result.
