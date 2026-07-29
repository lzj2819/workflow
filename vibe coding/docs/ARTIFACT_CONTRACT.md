# VeriLayer Artifact Contract v0.2 — Canonical Envelope

Status: v0.2 is the frozen canonical envelope. v0.3 is a versioned profile-decision record in `docs/contract-change-log.md`, not a second active envelope/schema version. Day 1 Gate remains **NO-GO** until evidence and four-party sign-off are complete.
Owner: A (Integration Owner and Contract Owner).  
Scope: the adapter boundary only; this document does not claim that production Adapters, Coding Executor, or Integration Executor already exist.

## 1. Purpose and normative sources

Every formal artifact exchanged between PRD, Architecture/Gherkin, Mocktest, Leaf, Coding, Integration, and Backfill must carry the canonical envelope below. Module-internal formats may remain unchanged behind their Adapter.

The Day 1 machine-readable source of truth is:

- `vibe coding/vibecode/schemas/verilayer-artifact.schema.json`

The existing `common-envelope.schema.json` and `module-result.schema.json` remain legacy workflow schemas; they are not altered in Day 1. When this document and the v0.2 schema conflict, the schema is authoritative until A records a versioned contract change. Unknown payload fields may be preserved by Adapters, but unknown status values must fail closed.

## 2. Canonical envelope

| Field | Requirement | Rule |
|---|---|---|
| `schema_version` | required string | Envelope/schema version. |
| `run_id` | required string | One logical workflow execution. |
| `project_id` | required string | Stable project namespace. |
| `node_id` | required string | The only formal cross-module child identity. |
| `parent_node_id` | required string or `null` | `null` only for the root node. |
| `artifact_id` | required string or `null` | Unique artifact identity within its node/run. |
| `artifact_type` | required enum | One of `prd`, `architecture`, `testcases`, `mocktest`, `leaf`, `code`, or `test_result`. |
| `status` | required enum | See Section 3. |
| `created_at` | required RFC 3339 date-time | Evidence creation time, not a later review time. |
| `generator` | required object/string/null | Tool, model, or human provenance. |
| `input_artifacts` | required string array | Repository-relative artifact references only. |
| `requirement_ids` | required string array | Requirement traceability identifiers. |
| `content_path` | required string or `null` | Repository-relative path; `null` only when no safe content file exists. |
| `content_sha256` | required lowercase SHA-256 or `null` | Hash of canonical content file bytes; `null` only when `content_path` is `null`. |
| `error` | required object or `null` | `null` except for `ERROR`; see the required nested fields below. |

`child_node_id` is legacy input compatibility only. An Adapter may read it, but every formal output must emit `node_id` and must not emit a different child identity.

## 3. Status and failure semantics

Allowed envelope statuses are `PENDING`, `RUNNING`, `PASS`, `FAIL`, `ERROR`, `CONTINUE_LAYERING`, `STOP_LAYERING`, and `COMPLETED`.

- `PASS` and `FAIL` are business/validation conclusions.
- `ERROR` is a tool, environment, schema, or system failure; it must never be silently converted to `FAIL` or `STOP_LAYERING`.
- `CONTINUE_LAYERING` and `STOP_LAYERING` are Leaf decisions only. A `STOP_LAYERING` result must have complete PRD, Architecture, Testcases, and Mocktest identity evidence.
- A strict audit `PASS` proves execution evidence completeness only. It does not override an Architecture or Mocktest `FAIL`.
- Any unknown status, missing identity, or unverifiable hash is an `ERROR` and blocks downstream Coding/Integration.

An error artifact is still a formal artifact and therefore carries the envelope with a non-null:

```text
error.category
error.code
error.message
```

The message must be redacted: no real secret, token, cookie, or personal absolute path may be placed in it.

## 4. Seven artifact profiles

All seven formal types use the exact envelope fields above. The following payload fields are expected after B/C/D review; they are extensions, not a license to omit envelope fields.

| Type | Payload minimum | Owner for proposal |
|---|---|---|
| PRD | requirement text/model and traceability | A |
| Architecture | components, interfaces, dependencies, data/state, risks, mappings, integration points | B |
| Testcases | features, scenarios, testcase IDs, preconditions, expected results, verification status | B |
| Mocktest | semantic conclusion, execution-completeness evidence, findings/defects | C |
| Leaf | decision, upstream evidence references, proposed children using `node_id` | C |
| Code | changed paths, workspace/patch evidence, executor provenance | D |
| TestResult | pytest/test evidence, repair evidence, result summary | D |

## 5. Module result compatibility contract

Each external module invocation returns a `module-result` extending the envelope. It must include:

```text
module
input_hash                    # lowercase SHA-256
output_artifacts              # repository-relative paths
output_hashes                 # path -> lowercase SHA-256
duration_ms
error_type
error_message
```

For `status=PASS`, `output_hashes` is mandatory. For `FAIL` or `ERROR`, retain the input hash, error classification, command/exit evidence where applicable, and any safely produced output paths. Do not delete negative results.

## 6. Required artifact gates

| Handoff | Minimum inputs | Required output/gate |
|---|---|---|
| PRD → Architecture/Gherkin | canonical envelope + requirement IDs | same `run_id/project_id/node_id`; artifacts carry hashes |
| Architecture/Gherkin → Mocktest | PRD, architecture, testcases | semantic result and strict execution evidence remain distinct |
| Mocktest → Leaf | four formal artifacts | identity must match; non-PASS or incomplete evidence blocks Coding |
| Leaf CONTINUE → child PRD | parent PRD + architecture + target module | child has a new `node_id` and correct `parent_node_id` |
| Leaf STOP → Coding/Test | Leaf decision + validated upstream evidence | code, patch/test evidence, and output hashes |
| children → Integration/Backfill | all completion packages | parent interface and child hashes verified before merge |

The seven migration fixture types are PRD, architecture, testcases, Mocktest report, Leaf decision, code, test result, and their enclosing module result/evidence records. Tutor fixtures are read-only migration evidence; they are not formal C0-C5 data or Leaf ground truth.

## 7. Path, privacy, and experiment controls

- Shared artifacts use repository-relative paths only. Historical absolute paths may be described in a provenance report, never used as executable configuration.
- Hidden tests remain physically isolated from shared packages and coding-agent context.
- `generator` records a logical tool/model identity and version where available; unavailable token/time values are `null`, not estimates.
- C0-C5 must use the same Coding Executor identity, model/settings, prompt template, token cap, and repair limit. The maximum repair limit is two rounds.
- Every content hash is recomputed after an Adapter writes or normalizes an artifact. A mismatch blocks downstream work.

### Content hash canonicalization

- For non-JSON content, `content_sha256` is SHA-256 over the original file bytes.
- For a JSON artifact that contains its own `content_sha256`, remove only that top-level field; serialize the remaining value with sorted keys, compact separators, UTF-8, and `ensure_ascii=false`; hash those canonical bytes.
- Both `content_path` and `content_sha256` are `null` only when no safely written content file exists. A missing or mismatched hash is an `ERROR`, never a `PASS` or a fabricated value.

This artifact-content hash rule is separate from the Day 1 environment installation-input rule in `docs/DAY1_GATE_STATUS.md`. That rule freezes requirements Git blob bytes and does not alter the active v0.2 envelope or schema.

## 8. Change control

A contract-affecting change requires a versioned change request and a `contract-diff` result before merge. The permitted outcomes are `MATCH`, `ADDITIVE_ONLY`, `ADAPTER_NEEDED`, `LEAF_FIX_REQUIRED`, and `CONTRACT_CHANGE_REQUIRED`.

- `MATCH` or reviewed `ADDITIVE_ONLY` may proceed.
- `ADAPTER_NEEDED`, `LEAF_FIX_REQUIRED`, and `CONTRACT_CHANGE_REQUIRED` block the affected edge until A records resolution.
- B/C/D do not directly change this contract. They submit a field proposal with sample artifact, schema validation result, input/output hashes, compatibility impact, and required downstream action.

## 8.1 v0.3 profile decisions — evidence verification pending

- Architecture: components, interfaces, dependencies, data/state, risks, requirement mappings, integration points, and child recursive context.
- Testcases: Features, scenarios, testcase records, a requirement-model path/hash, and validator evidence. Local `verification_status` never replaces envelope `status`.
- Mocktest/Leaf: `execution.completeness`, `execution.strict_audit_status`, `semantic_status`, `downstream_gate`, and `proposed_children[].node_id`.
- `input_artifacts` remains a string array of repository-relative references. Detailed typed references belong in the type-specific payload.
- Code/TestResult field groups are conditionally accepted in the v0.3 change log; their samples and environment evidence are not yet accepted as a Gate PASS.

## 9. Day 1 review checklist

- Verify all seven fixture types against the envelope/profile rules.
- Verify one migration example preserves `run_id/project_id/node_id/parent_node_id` and hashes.
- Verify `ERROR`, strict execution completeness, and semantic `FAIL` remain distinguishable.
- Verify no artifact configuration contains a member-local absolute path or secret.
- Record approval, rejection, or a versioned change request before Adapter implementation begins.
