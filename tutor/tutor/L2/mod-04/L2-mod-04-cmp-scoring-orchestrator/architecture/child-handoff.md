# Leaf Gate Override ? CMP-SCORING-ORCHESTRATOR

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-SCORING-ORCHESTRATOR

This package refines the exact parent node `CMP-SCORING-ORCHESTRATOR` inside `architecture/L1/L1-mod-04`. The next invocation must use one exact `child_id` below as `target_node_id` and this package root as `parent_architecture`.

## 1. Current node and parent binding

- Responsibility: CT-004 task ingestion, scoring-task lifecycle, lease coordination, one retry, deadline tracking, terminal result transaction, and CT-005 outcome coordination.
- Exclusions: assessment execution, prompt composition, direct model calls, Outbox dispatch, MOD-02/MOD-05 state, new public boundaries, new deployables, and parent-level technology changes.
- Parent binding: `ST-001`, `ST-002`, `CT-004`, `CT-005`, `CT-010`, `ICT-001..008`, `KD-001..003`, L1 `LCD-001..004`, `DU-3`.
- Boundary fingerprint: `L1-MOD-04/CMP-SCORING-ORCHESTRATOR|REQ-D002|ST-001|ST-002|CT-004|CT-005|CT-010|ICT-001..008|KD-001..003|DU-3`.

## 2. Next-level child registry

These exact IDs are the only current-level children and are sorted for stable handoff.

| child_id | Responsibility | Direct trace | State | Recommended entry condition |
|---|---|---|---|---|
| `CMP-SO-CLAIM-LEASE` | Conditional claim, lease expiry, reclaim_count, one active worker | `REQ-DD002`, `REQ-D002`, `ST-001`, `ICT-001`, `LCD-002` | `L2-ST-001-LEASE` | After task ingress is accepted; consistency/concurrency focus |
| `CMP-SO-METRICS-FACADE` | ICT-008 read-only source view for SM-002/SM-003 | `SM-002`, `SM-003`, `ICT-008`, `ST-001`, `ST-002` | No independent state | After write-path boundaries are approved; observability focus |
| `CMP-SO-RETRY-CONTROLLER` | One classified retry, failure records, crash-loop cap | `REQ-DD002`, `REQ-D002`, `FR-012`, `DF-2`, `ICT-006`, `ST-001` | `L2-ST-001-RETRY` | After lifecycle/lease rules are approved; failure-semantics focus |
| `CMP-SO-TASK-INGRESS` | CT-004 deduplication, task creation, deadline initialization | `REQ-DD002`, `REQ-D002`, `CT-004`, `ST-001` | `L2-ST-001-CORE` | When CT-004 ingestion detail is needed |
| `CMP-SO-TERMINAL-COMMIT` | scored/scoring_failed transaction, immutable result, ICT-007 coordination | `REQ-DD002`, `D-AC-REQ-008-01`, `AC-REQ-007-01`, `CT-005`, `ICT-005`, `ICT-007`, `ST-001`, `ST-002` | `L2-ST-002-RESULT` plus terminal ST-001 fields | **Recommended first**; consistency-core focus |

`CMP-RESULT-PUBLISHER`, `CMP-ASSESSMENT-ENGINE`, `CMP-MODEL-SERVICE-ACL`, and `CMP-SCORING-METRICS` are inherited collaborators/support components, not child IDs for this handoff.

## 3. Contract registry

### Inherited contracts

| Contract | Role in this package | Realizing child |
|---|---|---|
| `CT-004` | Consume and deduplicate | `CMP-SO-TASK-INGRESS` |
| `CT-005` | Produce through inherited publisher/outbox path | `CMP-SO-TERMINAL-COMMIT` → `CMP-RESULT-PUBLISHER` |
| `CT-010` | Indirectly consumed through inherited ACL | `CMP-ASSESSMENT-ENGINE` / `CMP-MODEL-SERVICE-ACL` |
| `ICT-001..008` | Internal parent contracts | Mapped in `04-contracts-and-runtime.md` |

### Child-only contracts

`CSO-IC-001` through `CSO-IC-006` are scoped to this selected node and are defined in `04-contracts-and-runtime.md`. They must not be promoted to cross-module contracts without parent review.

## 4. State and decision handoff

- State slices: `L2-ST-001-CORE`, `L2-ST-001-LEASE`, `L2-ST-001-RETRY`, `L2-ST-002-RESULT`, and coordination-only `L2-ST-003-OUTBOX-COORD`.
- Inherited decisions: `KD-001`, `KD-002`, `KD-003`, L1 `LCD-001..004`, and `Q-001` as non-blocking parent item.
- Local decisions: `LCD-201..204` are decided here; `LCD-301` is delegated to next-level detail; `LCD-302` is implementation detail.
- Unresolved risks: model-output quality and provider availability remain operational risks; Q-001 retention wiring remains parent-owned; none blocks this package.

## 5. Required ancestor context for next invocation

The next child refinement requires this package, the current L2 PRD, and the direct parent L1 package. Preserve the ancestor chain `L1 MOD-04 → L2 CMP-SCORING-ORCHESTRATOR`. Re-read the selected child’s state slice, inherited contract mapping, local decision records, and the parent boundary fingerprint before any deeper decomposition.

## 6. Actual inventory and validation evidence

### Inputs actually resolved

- L2 PRD: `prd/L2-PRD/mod-04/L2-mod-04-cmp-scoring-orchestrator/prd.md`.
- Parent package: all seven architecture files under `architecture/L1/L1-mod-04` required for identity, boundary, state, contracts, decisions, and handoff.
- Parent package type: recursive child package; target match: exact stable ID, one logical node.
- Output safety: target directory was empty before generation; mode `new` used.

### Outputs actually generated

- `architecture-manifest.yaml`
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`

No `parent-change-request.md` was created because no parent-impacting change was requested or discovered.

### Checks performed

| Check | Result |
|---|---|
| Required input paths and output safety | Passed |
| Parent package type and unique target match | Passed |
| Parent boundary snapshot completeness | Passed |
| Requirement allocation and trace coverage | Passed |
| Child registry stable IDs and non-empty parent/current traces | Passed |
| State ownership and parent/sibling ownership preservation | Passed |
| Inherited contract field/owner/side-effect/version preservation | Passed |
| C1-C6 mapping | Passed |
| Success, failure/recovery, lifecycle flows | Passed |
| Decision queue has no unhandled `decide_now` or `return_to_parent` | Passed |
| Seven-file inventory and handoff cross-reference | Passed |

Incomplete items are non-blocking: parent Q-001 retention wiring and next-level detail decisions `LCD-301/LCD-302`. Blocking impact: none.

## Human Gate

Please review and approve this package. After approval, continue with one exact target, preferably:

`[NEXT CMP-SO-TERMINAL-COMMIT]`

