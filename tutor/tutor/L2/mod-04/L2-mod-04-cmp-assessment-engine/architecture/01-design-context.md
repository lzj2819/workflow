# 01 Design Context — CMP-ASSESSMENT-ENGINE

## 1. Resolved inputs and selected parent boundary

| Field | Resolved value |
|---|---|
| `current_prd` | `prd/L2-PRD/mod-04/L2-mod-04-cmp-assessment-engine/prd.md` |
| `parent_architecture` | `architecture/L1/L1-mod-04` |
| `target_node_id` | `CMP-ASSESSMENT-ENGINE` |
| `output_dir` | `architecture/L2/mod-04/L2-mod-04-cmp-assessment-engine` |
| `mode` | `new` |
| parent package type | recursive child package |
| deployment boundary | `DU-3 assessment-worker` |

The selected node is uniquely matched in the L1 decomposition and handoff. This package refines only the internals of that node. `MOD-04`, sibling modules, and the parent-owned public contracts remain binding.

## 2. Parent-boundary snapshot

### Responsibility

The node executes one assessment attempt: it coordinates prompt composition, obtains material contents through the read-only port, invokes the model through the ACL, validates the model response, assembles the result content, and reports either completion or failure to the scoring orchestrator.

### Exclusions

- Task creation, claiming, leasing, scheduling, retry count, terminal state transitions, and result persistence remain with `CMP-SCORING-ORCHESTRATOR`.
- Network access and vendor-specific behavior remain behind `CMP-MODEL-SERVICE-ACL`.
- Rubric/template ownership remains with `CMP-RUBRIC-PROMPT-COMPOSER`.
- Material ownership remains with MOD-02; the child only consumes `ICT-003`.
- CT-005 assembly/Outbox write remains with `CMP-RESULT-PUBLISHER` and the orchestrator terminal transaction.
- Teacher presentation and notification rendering remain with MOD-05.

### State and data ownership

`ST-001 ScoringTask`, `ST-002 AssessmentResult`, `ST-003 Outbox`, and `ST-004 RubricPolicy` are parent-owned or sibling-support state. This L2 owns no durable state. It may create short-lived in-memory evaluation context, normalized response, validated payload, and failure classification for one attempt.

### Inherited contracts

| Contract | Parent role | Binding meaning |
|---|---|---|
| `ICT-001` | upstream task claim | execution context contains the claimed task, attempt number, and deadline before local evaluation begins |
| `CT-004` | upstream event consumed by orchestrator | submission/task context is already persisted and deduplicated before execution |
| `CT-005` | parent-level publication | `scored` carries result fields; `scoring_failed` carries real failure and retry information |
| `CT-010` | external model call through ACL | one call is bounded by 3 minutes, uses minimized materials, and returns model result or classified error |
| `ICT-002` | consumed | prompt plus prompt/rubric versions |
| `ICT-003` | consumed | material contents and readability, read-only, MOD-02 ownership |
| `ICT-004` | consumed | model response or `MODEL_TIMEOUT`/`MODEL_ERROR`/`INVALID_RESPONSE_SCHEMA` |
| `ICT-005` | reported to orchestrator | validated result payload enters the scored terminal transaction |
| `ICT-006` | reported to orchestrator | classified failure enters parent retry/failed-terminal policy |

No identifier, owner, required field, side effect, failure meaning, or version is changed here.

### Relevant flows and boundaries

The child participates in `FLOW-004`, `FLOW-005`, `FLOW-006`, `FLOW-007`, `SCENARIO-012`, and `DF-2`. The local order is:

`ICT-001 execution context -> ICT-002 -> ICT-003 -> ICT-004 -> local validation/assembly -> ICT-005 or ICT-006`.

The siblings `MOD-01` and `MOD-03` are reference-only collaborators and are not redesigned.

### Inherited decisions and constraints

`KD-001` requires ACL isolation and material minimization. `KD-002` requires same-group deployment, task-table/Outbox consistency, and shared material storage without ownership transfer. `KD-003` requires basic operations and minimal logs. `LCD-003` requires prompt/rubric version capture. `LCD-004` defines the ten-minute metric window and does not force-kill an overdue task. The parent prohibits a new public API, message bus, workflow engine, distributed transaction, cache/search platform, or independent deployment unit.

## 3. Current PRD requirement allocation

| Requirement | Classification | Parent trace | L2 realization |
|---|---|---|---|
| `REQ-DD001` — produce A–E grade, five dimension rationales, and teacher suggestions | allocated | `REQ-D001`, `FR-008`, `AC-REQ-008-01` | coordinator, response validator, result assembler |
| `D-AC-REQ-008-01` — incomplete materials still produce a result and explain impact; advice is teacher-only | allocated | `AC-REQ-008-01` | prompt context preservation, missing-material impact, teacher-only marker, validated result payload |
| `SM-002` — on-time scoring rate ≥95% | inherited/refinable | parent metric and `NFR-003` | no local deadline policy; keep execution bounded and observable without changing parent metric semantics |
| `SM-003` — teacher scoring coverage ≥95% | inherited | parent metric | ensure every success/failure path reports to the orchestrator; metric computation remains parent support |
| PRD placeholder sections for system boundary/external dependencies/constraints | out-of-scope | parent package is authoritative | no new boundary or architecture decision is invented from placeholders |

No requirement is allocated to a sibling, and no current requirement requires a parent-change request.

## 4. Current-level drivers

| Driver ID | Driver | Evidence | Design consequence |
|---|---|---|---|
| `L2-AE-D001` | preserve five-dimension domain invariants | `REQ-DD001`, `FR-008`, `D-AC-REQ-008-01` | dedicated response validation before `ICT-005` |
| `L2-AE-D002` | keep the execution node stateless | L1 responsibility/exclusions, `ST-001`/`ST-002` ownership | transient context only; rerun after worker recovery |
| `L2-AE-D003` | keep parent retry and terminal consistency authoritative | `ICT-005`, `ICT-006`, `KD-002`, `DF-2` | classify and report errors; never schedule or persist a retry locally |
| `L2-AE-D004` | protect data minimization and auditability | `KD-001`, `LCD-003`, `KD-003` | use ACL, carry versions internally, redact material/student identifiers from logs |

## 5. Preflight, assumptions, and open questions

### Reusable parent capability

The L1 package already provides task orchestration, model ACL, prompt composer, material read port, result publisher, shared persistence, and deployment boundary. The L2 package adds only local refinement and child-only in-process collaboration.

### Assumptions

- The model response received through `ICT-004` is the only source for the proposed grade and rationales; the child never invents a grade when validation fails.
- `missing_items[]` is a business signal, not an `ICT-003` read error. It is preserved in prompt/result impact explanation while unreadable referenced material is reported as `MATERIAL_UNREADABLE`.
- `scored_at` is assigned when the validated result is reported to the orchestrator; durable timestamp ownership remains in the parent terminal transaction.

### Open/non-blocking items

- `Q-001` (parent retention deletion wiring) is recorded but not used by this node's current PRD.
- Prompt text, compression, physical schema, polling, lease values, vendor endpoint, and logging configuration are delegated or implementation details. They do not change this L2 boundary.

## 6. Handoff validation method

Before Human Gate, check the manifest against all seven generated files, extract every `child_id`, verify every child has a requirement/parent trace, compare inherited contract IDs and fields to the L1 source, verify parent state ownership is not reassigned, and inspect the success, failure/recovery, and worker-crash lifecycle flows for ownership violations.
