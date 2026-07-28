# VeriLayer Contract Change Log

## v0.2 — 2026-07-28 — Day 1 canonical artifact envelope

- Owner: A (Integration Owner + Contract Owner).
- Status: proposed for the Day 1 human Gate; no Adapter or Executor implementation is authorized by this entry.
- Scope: PRD, Architecture, Testcases, Mocktest, Leaf, Code, and TestResult artifacts at Adapter boundaries.

| Change | Compatibility | Required action |
|---|---|---|
| Add `verilayer-artifact.schema.json` as the canonical machine-readable envelope | additive to module-internal formats; required at cross-module boundaries | B/C/D map their module output through an Adapter in Day 2 |
| Require the common identity, provenance, content, and `error` fields on all seven artifact types | breaking for any future formal output missing a field | emit `null` for unavailable `content_path`, `content_sha256`, or `error`; do not omit fields |
| Canonicalize child identity on `node_id` | breaking for producers that emit `child_node_id` as their formal child key | Adapter may dual-read legacy `child_node_id`, then emit the child as `node_id` |
| Separate business `FAIL` from system/tool/schema `ERROR` | semantic clarification | C/D confirm their failure taxonomy and preserve negative evidence |

## Pending Day 1 review

- B: Architecture/Testcases payload fields and requirement-to-scenario mapping.
- C: strict execution-completeness fields, Leaf evidence, decision payload, and defect taxonomy.
- D: Code/TestResult/Evidence payload fields, pytest evidence, repair evidence, and hidden-test isolation.

No proposal under `vibe coding/docs/proposals/` was present when this entry was written. A will append a versioned entry before accepting a later proposal that changes this envelope, status semantics, or identity rules.

## v0.3 — 2026-07-28 — Profile review and content hash rule

- Owner: A (Integration Owner + Contract Owner).
- Status: accepted contract decision; implementation remains blocked until the Day 1 Gate.

| Proposal / change | Decision | Outcome | Required action |
|---|---|---|---|
| B Architecture profile: components, interfaces, dependencies, data/state, risks, requirement mappings, integration points, recursive context | accepted as profile extension | ADDITIVE_ONLY | B Adapter must map incomplete historical values without invention; missing production fields remain non-PASS |
| B Testcases/Feature/requirement-model profile and local `verification_status` | accepted as profile extension | ADDITIVE_ONLY | `verification_status` is local only and must not replace envelope `status` |
| C strict completeness, strict-audit state, semantic result, downstream gate, and canonical proposed children | accepted as Mocktest/Leaf profile extension | ADDITIVE_ONLY | C must emit `proposed_children[].node_id`; only semantic PASS plus complete strict evidence allows Leaf |
| C typed `input_artifacts` objects | rejected | MATCH | Keep the canonical envelope as repository-relative string references; use payload references for typed detail |
| C `tool_error` duplicate field | rejected as a separate canonical field | MATCH | Use the required envelope `error` object for tool/system/schema/path errors |
| D Code/TestResult/Evidence proposal | pending | CONTRACT_CHANGE_REQUIRED if it changes envelope/status/hash semantics | D must provide an accessible commit/diff and proposal before A can decide |
| `content_sha256` self-reference | accepted | ADDITIVE_ONLY | apply the canonical rule below in every Adapter and validator |

### Canonical content hash rule

1. For non-JSON content, hash the original file bytes with SHA-256.
2. For a JSON artifact itself, parse UTF-8 JSON, remove only top-level `content_sha256`, serialize with sorted keys, compact separators, UTF-8, and `ensure_ascii=false`, then hash those canonical bytes.
3. `content_path` and `content_sha256` are both `null` only when no safely written content file exists. No Adapter may invent a hash.
4. A mismatch is `ERROR` with an error code such as `CONTENT_HASH_MISMATCH`; it blocks the downstream gate.

This rule is implemented in `vibe coding/vibecode/artifact_contract.py` and covered by `vibe coding/tests/test_artifact_contract.py`. B/D must not use a different JSON hashing rule.

## v0.3 D profile review — 2026-07-28

- Source reviewed: `origin/verilayer/d-coding-experiments:vibe coding/docs/CODING_EXECUTOR_PROTOCOL.md`.

| D field group | Decision | Outcome | Constraint |
|---|---|---|---|
| Code: task/attempt/workspace/allowed paths/generated files/patch/before-after hashes/requirement map/executor provenance | accepted | ADDITIVE_ONLY | all paths remain repository-relative; no Executor implementation is approved by this decision |
| TestResult: public/private scope, structured argv, timing, exit/timeout, stdout/stderr/JUnit hashes, summary, tested requirements | accepted | ADDITIVE_ONLY | private acceptance is opaque: no private path, test name, content, assertion, or failure detail may enter shared evidence or repair input |
| Evidence: request/model-call/file/patch/test/repair/leak-audit records | accepted as a nested/attached profile | ADDITIVE_ONLY | the seven canonical artifact types remain unchanged; an Evidence record is attached to Code/TestResult/module-result rather than a new top-level `artifact_type` |
| Token usage and time/cost values | accepted nullable | ADDITIVE_ONLY | `null` requires an unavailable reason; no estimate may be fabricated |
| `artifact_type=code_request` as a new canonical type | rejected | MATCH | a request is Adapter-internal input; formal delivery uses existing canonical `code` and `test_result` types |
| Absolute shared paths, secret values, hidden-test leakage, overwritten attempts | rejected | LEAF_FIX_REQUIRED | the future D validator must fail closed |

## C strict backend recovery assignment — 2026-07-28

- Owner: C.
- Required head: `4e7d1b0` (after `fbd2d40`) or a fast-forward successor.
- Required PR target: `verilayer/a-contract-integration`, never `main`.
- Scope: restore only the nine files under `mocktest/src/mock_framework/models/` from the controlled source, with per-file SHA-256 reconciliation. No business-logic rewrite is authorized.
- Before requesting merge, C must redact member-local absolute paths from committed logs and provide text-readable evidence for:
  - `import mock_framework.models`;
  - `import mock_framework.models.validator`;
  - `main_session_strict_driver.py --help`.
- Until that PR is reviewed and merged into A's branch, strict execution remains `ERROR`/`tool-package defect`; it must not create a strict audit, invoke Leaf, invoke Coding, or assert an Architecture conclusion.
