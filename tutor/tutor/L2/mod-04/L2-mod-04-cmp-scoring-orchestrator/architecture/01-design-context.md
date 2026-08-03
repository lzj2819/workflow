# 01 Design Context — CMP-SCORING-ORCHESTRATOR

This package refines exactly one L1 node: `CMP-SCORING-ORCHESTRATOR` inside `L1-mod-04`. The parent package is binding. The current layer may choose internal ownership and collaboration, but it does not change MOD-04 boundaries, public contracts, state ownership outside the selected node, deployment, or sibling responsibilities.

## 1. Resolved inputs and preflight

| Input | Resolved value | Evidence / result |
|---|---|---|
| `parent_architecture` | `C:\Users\Lenovo\Desktop\codex_plugin\architecture\L1\L1-mod-04` | Readable recursive package with `architecture-manifest.yaml`; passed |
| `target_node_id` | `CMP-SCORING-ORCHESTRATOR` | Exact logical match in parent manifest, decomposition, and handoff; one node, passed |
| `current_prd` | `C:\Users\Lenovo\Desktop\codex_plugin\prd\L2-PRD\mod-04\L2-mod-04-cmp-scoring-orchestrator\prd.md` | Readable; `REQ-DD002 -> REQ-D002`; passed |
| `output_dir` | `C:\Users\Lenovo\Desktop\codex_plugin\architecture\L2\mod-04\L2-mod-04-cmp-scoring-orchestrator` | Directory existed but contained no package files; safe for `mode=new` |
| `mode` | `new` | No existing package was overwritten |

Reusable parent capability is the L1 task state machine, terminal transaction model, Outbox coordination, ACL delegation, metrics source, and DU-3 deployment boundary. No blocking gap was found. The parent PRD was not required because the parent package contains the selected node’s requirement, contract, flow, state, decision, and deployment traces.

Planned files are exactly the seven files listed in `architecture-manifest.yaml`. Handoff validation uses static inventory checks, YAML parsing, stable-ID comparison across registries, requirement/parent trace checks, and field-level comparison of inherited contract facts.

## 2. Parent-boundary snapshot

### 2.1 Identity, responsibility, and exclusions

| Item | Binding parent fact | Local treatment |
|---|---|---|
| Node | `CMP-SCORING-ORCHESTRATOR`, direct child of `MOD-04` | Keep identity unchanged; create only internal child IDs |
| Responsibility | Consume `CT-004`; create scoring tasks; own lifecycle; claim via lease; retry once; track ten-minute deadline; write terminal result/retry/Outbox transaction | Refine into five internal responsibility boundaries |
| Exclusions | No assessment execution, prompt composition, direct model call, event dispatch, new public API, or new deployable | Preserve; collaborators are referenced only through inherited contracts |
| Deployment | `DU-3 assessment-worker` | All children run inside the same inherited worker boundary |

### 2.2 State and data ownership

- `ST-001 ScoringTask` is owned by this selected node. Its stable external fields, lifecycle, attempt rules, lease fields, and retention/privacy constraints are inherited.
- `ST-002 AssessmentResult` is persisted by this selected node in the terminal transaction and assembled by `CMP-ASSESSMENT-ENGINE`. It is written once and immutable after persistence.
- `ST-003 Outbox` is owned by `CMP-RESULT-PUBLISHER` for the write protocol. The selected node provides terminal transaction context and invokes the inherited internal `ICT-007`; it does not claim ST-003 ownership.
- MOD-02 remains the owner of Submission and material state. MOD-05 remains the owner of review/presentation/notification state.
- The parent rules remain: encrypted storage, local-region processing, no material content or business identifiers sent to the model provider, and no parent-level deletion path invented locally.

#### 2.2.1 Terminal commit boundary

`CMP-SO-TERMINAL-COMMIT` owns the local transaction boundary for terminal outcomes. `CMP-RESULT-PUBLISHER` participates only in the same transaction for the inherited `ICT-007`/`ST-003` insertion and does not commit independently.

The terminal child accepts a completion callback only when all of the following guards hold: the task is currently `in_progress`; `task_id`/`submission_id` identify the same `ST-001` row; `attempt_no` equals the current classified attempt; the callback lease token is still active; and no terminal `ST-002` result or terminal outcome already exists. The callback adapter's task and lease correlation fields are local guard context and do not extend the parent `ICT-005` schema.

On a valid `ICT-005` callback, the transaction writes terminal `ST-001`, immutable `ST-002`, and the inherited `ST-003` Outbox row. On a second classified failure or inherited crash-loop cap, it writes terminal `ST-001` and the `ST-003` failure outcome without creating a grade. A stale, duplicate, invalid, or mismatched callback performs no business-state or Outbox write and emits only the local operational observation. Any failure in the terminal transaction rolls back all terminal writes and is surfaced through the inherited transaction-failure semantics.

### 2.3 Contracts and direct boundaries

| Parent contract | Selected-node role | Binding meaning |
|---|---|---|
| `CT-004 SubmissionReceived` | Consumer | Deduplicate by `submission_id`; persist the task before acknowledging the event |
| `CT-005 SubmissionScored/ScoringFailed` | Producer through `CMP-RESULT-PUBLISHER` | `outcome` is `scored` or `scoring_failed`; v=1; conditional fields are unchanged |
| `CT-010 model assessment` | Indirect consumer | Only the inherited ACL consumes it; this node sees classified assessment success/failure through internal callbacks |
| `ICT-001..008` | Inherited internal collaboration | IDs, owners, schemas, side effects, error semantics, idempotency, and compatibility remain unchanged |

Direct upstream is MOD-02 through `CT-004` and the material read port. Direct downstream is MOD-02/MOD-05 through `CT-005`, plus the external model service through the inherited ACL. MOD-01 and MOD-03 are sibling references only; their internals are not redesigned.

### 2.4 Parent flows and decisions

The local runtime must preserve the parent order: `CT-004` → task persistence → `ICT-001` claim → assessment execution → `ICT-005` or `ICT-006` → terminal transaction → `CT-005`. The failure path allows exactly one classified retry. A worker crash after claim reclaims the same attempt after lease expiry; it does not consume the business retry budget. `deadline_at = created_at + 10 minutes` is a measurement and tracking value, not a forced kill or fabricated failure.

Inherited decisions are `KD-001` (ACL and data minimization), `KD-002` (relational task table plus Outbox, no message bus), `KD-003` (encryption/backup/observability), and L1 `LCD-001..004`. `Q-001` remains a non-blocking parent-owned retention question. No current PRD requirement changes a parent responsibility, contract, ownership, dependency direction, technology decision, or deployment boundary.

## 3. Current PRD requirement allocation

| Current requirement / contract | Classification | Parent trace | Allocation in this node |
|---|---|---|---|
| `REQ-DD002` | allocated | `REQ-D002`, `FR-012`, `DF-2`, `AC-REQ-007-01` | Task creation, lifecycle, one retry, failure terminal, and outcome transaction; assessment execution remains outside this node |
| `D-AC-REQ-008-01` | allocated | Parent `D-AC-REQ-008-01`, `ST-002`, `CT-005` | Preserve and atomically persist the result fields supplied by the engine; publish the parent CT-005 projection |
| `SM-002` | inherited + allocated | Parent `SM-002`, `NFR-003`, `ICT-008` | Expose created-to-scored source timestamps to the inherited metrics consumer |
| `SM-003` | inherited + allocated | Parent `SM-003`, `ICT-008` | Expose terminal coverage and retry/failure source data without changing the metric definition |
| System boundary placeholder in current PRD | inherited | Parent MOD-04 exclusions and DU-3 | Use parent boundary; do not invent a new one |
| External dependency placeholder in current PRD | inherited | `CT-010`, `KD-001`, `CMP-MODEL-SERVICE-ACL` | Use the parent ACL path only |
| Explicit constraint placeholder in current PRD | inherited | `KD-002`, `KD-003`, L1 decisions | Preserve relational task/Outbox model and operational constraints |
| Teacher-facing display/notification implied by outcome | out-of-scope | Parent MOD-05 boundary and `CT-005` consumer semantics | Only emit the parent outcome; no UI or notification implementation here |

## 4. Local drivers

| Driver | Local consequence |
|---|---|
| Single-writer consistency | Keep task lifecycle and terminal outcome coordination within one selected node and one local transaction boundary |
| Idempotency | Separate event ingress deduplication, conditional lease acquisition, attempt deduplication, and terminal-outcome uniqueness |
| Failure semantics | Keep classified model/material/prompt failures distinct from worker crash recovery; only the former consumes the one retry |
| Interaction | Use in-process commands/callbacks and the inherited task-table coordination; no new message bus |
| Observability | Derive metrics from ST-001/ST-002 timestamps and outcomes; do not log material content or student identifiers |
| Lifecycle | Make pending, claimed, retryable, scored, scoring_failed, lease-expired, and crash-reclaimed transitions explicit without adding public states |

## 5. Assumptions and open items

- The current PRD’s placeholder architecture-input sections are satisfied by the authoritative parent package; they are not permission to invent alternate boundaries.
- Concrete SQL indexes, polling cadence, exact lease duration, and framework/configuration choices are delegated to the next level and do not change this package’s architecture.
- `Q-001` is recorded as inherited and non-blocking because the current PRD does not require retention deletion.
