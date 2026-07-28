# 05 Local Decisions — CMP-SCORING-ORCHESTRATOR

This queue contains only decisions discovered while refining the selected node. Parent decisions are inherited and clearly marked; parent-owned choices are not re-decided locally.

## 1. Inherited decisions

| Source | Binding decision | Local consequence |
|---|---|---|
| `KD-001` | External model API is isolated behind the MOD-04 ACL; data is minimized and providers are replaceable | No child calls CT-010 directly or sends business identifiers |
| `KD-002` | Relational task table plus Outbox; no message bus or distributed transaction | Child collaboration is in-process and terminal writes use one local transaction |
| `KD-003` | Local-region processing, encrypted storage, backup and inherited monitoring | No new storage/region/observability platform is chosen here |
| L1 `LCD-001` | Material access uses the MOD-02-owned read-only port | No material state ownership moves into this node |
| L1 `LCD-002` | One bounded retry; crash reclaim does not spend attempt budget | RETRY-CONTROLLER and CLAIM-LEASE keep separate counters |
| L1 `LCD-003` | Prompt/rubric versions are stored internally with results | Terminal commit preserves version fields but does not design prompt support |
| L1 `LCD-004` | Ten-minute deadline is tracking/measurement, not hard kill | Deadline policy cannot fabricate `scoring_failed` |
| `Q-001` | Parent retention deletion wiring is unresolved and not connected to this node | Record as non-blocking; do not create a local deletion path |

## 2. Local decision queue

| Decision ID | Source artifact | Source ID | Affected child artifact | Why mapping is not enough | Classification | Follow-up target |
|---|---|---|---|---|---|---|
| `LCD-201` | 02-decomposition | C1/C2 | All five children | A responsibility/state split is required for stable ownership and child handoff | decide_now | This package §3 |
| `LCD-202` | 03-state-and-data | ST-001/ST-002 | TERMINAL-COMMIT | Parent atomicity requires one local coordinator rather than separate result and event writers | decide_now | This package §3 |
| `LCD-203` | 04-contracts-and-runtime | ICT-001/ICT-006 | CLAIM-LEASE, RETRY-CONTROLLER | Parent contracts do not prescribe the internal callback boundary between lease recovery and classified retry | decide_now | This package §3 |
| `LCD-204` | 04-contracts-and-runtime | ICT-008 | METRICS-FACADE | A read-only source boundary is needed to keep metrics off the write path | decide_now | This package §3 |
| `LCD-301` | 04-contracts-and-runtime | ICT-001/ICT-008 | CLAIM-LEASE, METRICS-FACADE | Physical indexes, poll cadence, lease duration, and log field mapping are detail choices | defer_to_next_level | L3 refinement of `CMP-SO-CLAIM-LEASE` and `CMP-SO-METRICS-FACADE` |
| `LCD-302` | 03-state-and-data | ST-001/ST-002 | TASK-INGRESS, TERMINAL-COMMIT | Exact table schema, ORM, transaction API, and framework configuration are implementation details | implementation_detail | Detailed design/implementation; no parent impact |

There are no `return_to_parent` decisions. No current requirement asks to alter a parent contract, ownership, dependency direction, ADR, technology, deployment, or public boundary.

## 3. Local decision records

### LCD-201 — Responsibility and state-slice decomposition

Decision: use five child boundaries: task ingress, claim/lease, retry control, terminal commit, and metrics facade. This is preferable to generic controller/service/repository layers because each child has a distinct invariant or change reason. A single orchestration child would hide concurrency and terminal atomicity; a layer-only split would not provide stable state ownership. The choice remains inside the selected node.

### LCD-202 — Single terminal commit coordinator

Decision: `CMP-SO-TERMINAL-COMMIT` is the only child allowed to coordinate the terminal transition. It writes ST-001 terminal fields, ST-002, and inherited ICT-007 context atomically. Splitting result persistence and event publication into independent child writers would weaken the parent’s consistency invariant, so it is rejected.

### LCD-203 — Separate crash reclaim from business retry

Decision: `CMP-SO-CLAIM-LEASE` owns lease expiry/reclaim and `CMP-SO-RETRY-CONTROLLER` owns classified attempt progression. A reclaim preserves `attempt_no` and increments `reclaim_count`; a classified failure changes attempt state. Combining them would make crash recovery consume the one business retry or make retry decisions depend on worker liveness.

### LCD-204 — Read-only metrics facade

Decision: provide ICT-008 through `CMP-SO-METRICS-FACADE`, sourcing ST-001/ST-002 and never writing business state. This makes SM-002/SM-003 traceable while isolating observability queries from the scoring write path. It is not a new public API, datastore, or metrics platform.

## 4. Prohibited parent-owned decisions

The following are explicitly prohibited locally: changing CT-004/CT-005/CT-010 identifiers or schemas; moving Submission/material/result ownership across MOD-02/MOD-04/MOD-05; adding a public network contract; introducing a message bus, distributed transaction, separate service, or deployment unit; changing DU-3; changing KD-001/KD-002/KD-003; or inventing the Q-001 retention flow. Any such request would require `parent-change-request.md` and a blocked run.

