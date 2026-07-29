# VeriLayer Contract Change Log

## v0.2 — 2026-07-28 — Day 1 canonical artifact envelope

- Owner: A (Integration Owner + Contract Owner).
- Status: historical envelope decision. Its review-status wording is superseded by the 2026-07-29 Gate reconciliation below; no Adapter or Executor implementation is authorized by this entry.
- Scope: PRD, Architecture, Testcases, Mocktest, Leaf, Code, and TestResult artifacts at Adapter boundaries.

| Change | Compatibility | Required action |
|---|---|---|
| Add `verilayer-artifact.schema.json` as the canonical machine-readable envelope | additive to module-internal formats; required at cross-module boundaries | B/C/D map their module output through an Adapter in Day 2 |
| Require the common identity, provenance, content, and `error` fields on all seven artifact types | breaking for any future formal output missing a field | emit `null` for unavailable `content_path`, `content_sha256`, or `error`; do not omit fields |
| Canonicalize child identity on `node_id` | breaking for producers that emit `child_node_id` as their formal child key | Adapter may dual-read legacy `child_node_id`, then emit the child as `node_id` |
| Separate business `FAIL` from system/tool/schema `ERROR` | semantic clarification | C/D confirm their failure taxonomy and preserve negative evidence |

## Historical pending-review list

- B: Architecture/Testcases payload fields and requirement-to-scenario mapping.
- C: strict execution-completeness fields, Leaf evidence, decision payload, and defect taxonomy.
- D: Code/TestResult/Evidence payload fields, pytest evidence, repair evidence, and hidden-test isolation.

This list predates the received B/C/D proposals and is superseded as a status summary by the 2026-07-29 Gate reconciliation. A will append a versioned entry before accepting a later proposal that changes this envelope, status semantics, or identity rules.

## v0.3 — 2026-07-28 — Profile review and content hash rule

- Owner: A (Integration Owner + Contract Owner).
- Status: field decisions accepted; profile evidence and human Gate approval remain pending. This is not a Day 1 Gate PASS and does not authorize execution.

| Proposal / change | Decision | Outcome | Required action |
|---|---|---|---|
| B Architecture profile: components, interfaces, dependencies, data/state, risks, requirement mappings, integration points, recursive context | accepted as profile extension | ADDITIVE_ONLY | B Adapter must map incomplete historical values without invention; missing production fields remain non-PASS |
| B Testcases/Feature/requirement-model profile and local `verification_status` | accepted as profile extension | ADDITIVE_ONLY | `verification_status` is local only and must not replace envelope `status` |
| C strict completeness, strict-audit state, semantic result, downstream gate, and canonical proposed children | accepted as Mocktest/Leaf profile extension | ADDITIVE_ONLY | C must emit `proposed_children[].node_id`; only semantic PASS plus complete strict evidence allows Leaf |
| C typed `input_artifacts` objects | rejected | MATCH | Keep the canonical envelope as repository-relative string references; use payload references for typed detail |
| C `tool_error` duplicate field | rejected as a separate canonical field | MATCH | Use the required envelope `error` object for tool/system/schema/path errors |
| D Code/TestResult/Evidence proposal | superseded by the D review below | see v0.3 D profile review | D must still provide accepted samples and a reviewable environment evidence package |
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
- Historical required head: `4e7d1b0` (after `fbd2d40`) or a fast-forward successor.
- Required PR target: `verilayer/a-contract-integration`, never `main`.
- Scope: restore only the nine files under `mocktest/src/mock_framework/models/` from the controlled source, with per-file SHA-256 reconciliation. No business-logic rewrite is authorized.
- Before requesting merge, C must redact member-local absolute paths from committed logs and provide text-readable evidence for:
  - `import mock_framework.models`;
  - `import mock_framework.models.validator`;
  - `main_session_strict_driver.py --help`.
- PR #5 is now merged into A. Package restoration does not change the strict result: until a frozen-environment strict run completes, strict completeness is `NOT_RUN`, semantic status is `NOT_RUN`, and Leaf/Coding remain blocked.

## 2026-07-29 Day 1 Gate reconciliation

- Active envelope: **v0.2** only. v0.3 names accepted profile-field decisions in this log; it does not replace the v0.2 schema version.
- Gate decision: **NO-GO**. Field acceptance, models restoration, a fixture, `--help`, xfail, Tutor material, or an unmerged environment report is not real E2E or Coding authorization.
- PR #3 (B): open and unmerged. Its seven-file proposal/fixture-only scope is acceptable for Day 1 review, but it is not fresh B output and its samples must validate in the current-A frozen environment.
- PR #4 (D): closed and unmerged. Its environment records use raw requirements hash `464c4c…e76e03`, which differs from current-A raw hash `f55ab0…ad472`; the records are not accepted as current-A environment evidence.
- PR #5 (C models): merged into A at `c12c4f5`. This accepts package restoration only; current smoke remains `ENVIRONMENT_ERROR`, and strict completeness/semantic result are both `NOT_RUN`.

### 2026-07-29 addendum: environment-input and full-Gate decision

- v0.2 is the sole active envelope. v0.3 remains only the profile-field decision record above.
- Canonical environment input is SHA-256 over the Git blob bytes at `c12c4f5:vibe coding/requirements-verilayer.txt`: `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472`.
- Earlier wording in this log or the Gate status that labelled D's `464c4c...e76e03` working-file observation stale is superseded. It may be a different Windows checkout byte stream; it is noncanonical, not classified false or stale without byte/EOL-policy proof.
- `tests/integration` is absent. Its pytest exit `4` is an acceptance-spec `ERROR`; it is not a PASS. The current Day 1 executable Gate omits that path until a real reviewed suite is added.

### 2026-07-29 Day 1 scope correction

- The active Day 1 checklist is defined only in `docs/DAY1_GATE_STATUS.md`.
- Day 1 evidence is limited to Contract v0.2, D frozen-environment evidence using the canonical Git-blob digest, B proposal/fixture review, and C's three smoke commands.
- Fresh B output, complete strict execution, semantic PASS/FAIL, Leaf, Coding, and `tests/integration` are deferred to Day 3 or later. They must not be used to block or claim Day 1 completion.

## 2026-07-29 Day 1 environment-input closure

- This entry does not modify the frozen v0.2 envelope, schema, identity rule, or status semantics.
- Current-A smoke revealed that the declared Mocktest runtime imports require `PyYAML==6.0.2`, `rich==13.9.4`, and `gherkin-official==24.1.0`. They were added to `vibe coding/requirements-verilayer.txt` in `8766793`.
- The current canonical installation input is the Git blob at `8766793:vibe coding/requirements-verilayer.txt`, SHA-256 `370d4e7bd1ae9df0ede903ac4741c5f1fd4c02a53b13eb0e732c380a10ba0bc6`. Earlier requirement hashes remain historical evidence for their earlier inputs only.
- The four narrowed Day 1 items are closed on that baseline. The resulting GO authorizes Day 2 skeleton work only; it is not strict, semantic, Leaf, Coding, E2E, or experiment evidence.
