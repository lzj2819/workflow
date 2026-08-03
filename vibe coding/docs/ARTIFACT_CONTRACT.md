# VeriLayer Artifact Contract v0.1

Status: Day 1 draft, frozen for cross-module integration review.  
Owner: A (Integration Owner and Contract Owner).  
Scope: the adapter boundary only; this document does not claim that production Adapters, Coding Executor, or Integration Executor already exist.

## 1. Purpose and normative sources

Every formal artifact exchanged between PRD, Architecture/Gherkin, Mocktest, Leaf, Coding, Integration, and Backfill must carry the canonical envelope below. Module-internal formats may remain unchanged behind their Adapter.

Machine-readable sources of truth are:

- `vibe coding/vibecode/schemas/common-envelope.schema.json`
- `vibe coding/vibecode/schemas/module-result.schema.json`
- `vibe coding/vibecode/schemas/contract.schema.json`

When this document and a schema conflict, the schema is authoritative until A publishes a versioned contract change. Unknown fields may be preserved by Adapters, but unknown status values must fail closed.

## 2. Canonical envelope

| Field | Requirement | Rule |
|---|---|---|
| `schema_version` | required string | Envelope/schema version. |
| `run_id` | required string | One logical workflow execution. |
| `project_id` | required string | Stable project namespace. |
| `node_id` | required string | The only formal cross-module child identity. |
| `parent_node_id` | required string or `null` | `null` only for the root node. |
| `artifact_id` | required string or `null` | Unique artifact identity within its node/run. |
| `artifact_type` | required string or `null` | PRD, architecture, testcases, mocktest report, leaf decision, code, test result, module result, or evidence. |
| `status` | required enum | See Section 3. |
| `created_at` | required RFC 3339 date-time | Evidence creation time, not a later review time. |
| `generator` | required object/string/null | Tool, model, or human provenance. |
| `input_artifacts` | required string array | Repository-relative artifact references only. |
| `requirement_ids` | required string array | Requirement traceability identifiers. |
| `content_path` | required by artifact profile | Repository-relative path; no personal drive or user-home path. |
| `content_sha256` | required by artifact profile | Lowercase SHA-256 of canonical file bytes. |

`child_node_id` is legacy input compatibility only. An Adapter may read it, but every formal output must emit `node_id` and must not emit a different child identity.

## 3. Status and failure semantics

Allowed envelope statuses are `PENDING`, `RUNNING`, `PASS`, `FAIL`, `ERROR`, `CONTINUE_LAYERING`, `STOP_LAYERING`, and `COMPLETED`.

- `PASS` and `FAIL` are business/validation conclusions.
- `ERROR` is a tool, environment, schema, or system failure; it must never be silently converted to `FAIL` or `STOP_LAYERING`.
- `CONTINUE_LAYERING` and `STOP_LAYERING` are Leaf decisions only. A `STOP_LAYERING` result must have complete PRD, Architecture, Testcases, and Mocktest identity evidence.
- A strict audit `PASS` proves execution evidence completeness only. It does not override an Architecture or Mocktest `FAIL`.
- Any unknown status, missing identity, or unverifiable hash is an `ERROR` and blocks downstream Coding/Integration.

An error artifact is still a formal artifact and therefore carries the envelope plus:

```text
error.category
error.code
error.message
```

The message must be redacted: no real secret, token, cookie, or personal absolute path may be placed in it.

## 4. Module result contract

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

## 5. Required artifact profiles and gates

| Handoff | Minimum inputs | Required output/gate |
|---|---|---|
| PRD → Architecture/Gherkin | canonical envelope + requirement IDs | same `run_id/project_id/node_id`; artifacts carry hashes |
| Architecture/Gherkin → Mocktest | PRD, architecture, testcases | semantic result and strict execution evidence remain distinct |
| Mocktest → Leaf | four formal artifacts | identity must match; non-PASS or incomplete evidence blocks Coding |
| Leaf CONTINUE → child PRD | parent PRD + architecture + target module | child has a new `node_id` and correct `parent_node_id` |
| Leaf STOP → Coding/Test | Leaf decision + validated upstream evidence | code, patch/test evidence, and output hashes |
| children → Integration/Backfill | all completion packages | parent interface and child hashes verified before merge |

The seven migration fixture types are PRD, architecture, testcases, Mocktest report, Leaf decision, code, test result, and their enclosing module result/evidence records. Tutor fixtures are read-only migration evidence; they are not formal C0-C5 data or Leaf ground truth.

## 6. Path, privacy, and experiment controls

- Shared artifacts use repository-relative paths only. Historical absolute paths may be described in a provenance report, never used as executable configuration.
- Hidden tests remain physically isolated from shared packages and coding-agent context.
- `generator` records a logical tool/model identity and version where available; unavailable token/time values are `null`, not estimates.
- C0-C5 must use the same Coding Executor identity, model/settings, prompt template, token cap, and repair limit. The maximum repair limit is two rounds.
- Every content hash is recomputed after an Adapter writes or normalizes an artifact. A mismatch blocks downstream work.

## 7. Change control

A contract-affecting change requires a versioned change request and a `contract-diff` result before merge. The permitted outcomes are `MATCH`, `ADDITIVE_ONLY`, `ADAPTER_NEEDED`, `LEAF_FIX_REQUIRED`, and `CONTRACT_CHANGE_REQUIRED`.

- `MATCH` or reviewed `ADDITIVE_ONLY` may proceed.
- `ADAPTER_NEEDED`, `LEAF_FIX_REQUIRED`, and `CONTRACT_CHANGE_REQUIRED` block the affected edge until A records resolution.
- B/C/D do not directly change this contract. They submit a field proposal with sample artifact, schema validation result, input/output hashes, compatibility impact, and required downstream action.

## 8. Day 1 review checklist

- Verify all seven fixture types against the envelope/profile rules.
- Verify one migration example preserves `run_id/project_id/node_id/parent_node_id` and hashes.
- Verify `ERROR`, strict execution completeness, and semantic `FAIL` remain distinguishable.
- Verify no artifact configuration contains a member-local absolute path or secret.
- Record approval, rejection, or a versioned change request before Adapter implementation begins.
