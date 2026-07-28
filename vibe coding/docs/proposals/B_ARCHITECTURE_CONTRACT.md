# B proposal: Architecture contract (Day 1)

Status: proposed for A's review; not a production Adapter or shared-schema change.

## Audit scope and finding

The read-only migration set contains 22 Feature files (one L0, five L1, and sixteen L2) and 16 paired L2 `architecture.json` / `testcases.json` artifacts. Every historic architecture artifact has the v0.1 envelope fields `schema_version`, `run_id`, `project_id`, `node_id`, `parent_node_id`, `artifact_id`, `artifact_type`, `created_at`, `generator`, `status`, `input_artifacts`, and `requirement_ids`.

Historic architecture payload coverage is limited to `components`, `interfaces`, `dependencies`, `depth`, `complexity`, `risks`, `responsibility`, and `children`. In the 16 L2 examples, `components`, `interfaces`, and `dependencies` are string-ID lists, `children` is empty, and there is no machine-readable state, integration, interface, or requirement mapping detail. The historical generator is `structured-input-preparer`; these are migration fixtures, not production-generation evidence.

## Proposed `architecture.json` profile

The artifact MUST carry A's canonical envelope. The payload below is the minimum B profile; all references are stable IDs or repository-relative paths.

| Field | Required | Purpose |
|---|---:|---|
| `components` | yes | Objects with `component_id`, `name`, `responsibility`, `owned_state_ids`, `requirement_ids`, and `status`. |
| `interfaces` | yes | Objects with `contract_id`, `provider`, `consumer`, `trigger`, `protocol`, `sync_mode`, `schema_ref`, `side_effects`, `dependencies`, `error_timeout_retry`, `idempotency`, `version`, and `requirement_ids`. |
| `dependencies` | yes | Directed objects with `from_component_id`, `to_component_id`, `dependency_type`, `reason`, and `requirement_ids`. |
| `data_and_state` | yes | State records with `state_id`, `owner_component_id`, readers, writers, lifecycle, consistency boundary, retention/privacy constraint, and requirement trace. |
| `risks` | yes | Records with `risk_id`, `description`, `severity`, `mitigation`, `status`, and requirement/component trace. |
| `requirement_mappings` | yes | One or more `requirement_id` to component/interface/state/risk references, with `coverage_status`. |
| `integration_points` | yes | External or cross-module touchpoints with owner, direction, contract reference, failure policy, and trace. |
| `recursive_context` | required for a child | `target_node_id`, `parent_node_id`, `parent_artifact_ref`, `boundary_fingerprint`, inherited-fixed/refinable/delegated items, and `node_match_evidence`. |
| `children` | yes | Objects with `child_id`, responsibility, exclusions, owned state, requirement IDs, dependencies, reason, and next-entry status. |

Empty arrays are allowed only where semantically valid; required mapping and ownership information must not be replaced by descriptive prose. `node_id` remains the only cross-module child identity; do not emit a distinct `child_node_id`.

## Seven-file recursive package mapping

The package remains exactly: `architecture-manifest.yaml`, `01-design-context.md`, `02-architecture-decomposition.md`, `03-state-and-data.md`, `04-contracts-and-runtime.md`, `05-local-decisions.md`, and `child-handoff.md`. The JSON profile is the machine-readable handoff projection, not a substitute for those seven files.

| Package source | Required projection |
|---|---|
| manifest + design context | recursive context, identity, input artifact refs, boundary fingerprint, status |
| decomposition | components, children, dependencies, requirement mappings |
| state and data | `data_and_state` |
| contracts and runtime | interfaces and integration points |
| local decisions | risks and decision status |
| child handoff | child IDs and next-level entry status |

## S1 contract-only example

`vibe coding/tests/fixtures/contracts/architecture.example.json` is a fresh, non-Tutor S1 example. It exists to test this proposed profile only and must never be reported as generated Architecture or benchmark evidence.

## Requested A decision

Requested field/change: add the nine payload field groups above as the Architecture artifact profile under the existing envelope.

Reason: the migration payload cannot demonstrate state ownership, recursive boundary inheritance, interface semantics, or requirement-level traceability needed by Mocktest, Leaf, and Coding.

Backward compatibility: Adapter may ingest historic string lists and emit `ADAPTER_NEEDED`; it must not fabricate missing mappings. New profile fields are additive to the envelope, but are required for a production Architecture handoff.

Required downstream action: C consumes requirement mappings, interface/error semantics, and risks; D consumes components, dependencies, interfaces, state ownership, and requirements. A must version/approve the profile before B writes a production Adapter.
