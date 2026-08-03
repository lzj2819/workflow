# 03 State and Data — CMP-SCORING-ORCHESTRATOR

The parent node owns `ST-001` and `ST-002`. This document refines internal state slices without creating a new persisted schema, transferring ownership, or changing parent retention/privacy rules. `ST-003` remains owned by `CMP-RESULT-PUBLISHER`; the terminal child only coordinates its inherited write protocol.

## 1. State ownership registry

Stable local state identifiers are sorted. Each local identifier names a semantic slice of an inherited state, not a new cross-node contract.

| state_id | State slice | owner child_id | Readers | Writers | Lifecycle | Consistency boundary | Retention/privacy | Parent trace |
|---|---|---|---|---|---|---|---|---|
| `L2-ST-001-CORE` | Task identity/input snapshot, `submission_id`, assignment/material refs, status timestamps, deadline_at | `CMP-SO-TASK-INGRESS` | CLAIM-LEASE, RETRY-CONTROLLER, TERMINAL-COMMIT, METRICS-FACADE | TASK-INGRESS; terminal child for terminal status | absent → pending → in_progress → terminal | `submission_id` uniqueness and task-row transaction | Parent ST-001 retention; encrypted/local-region; no provider egress of business identifiers | `ST-001`, `CT-004`, `REQ-D002` |
| `L2-ST-001-LEASE` | `claim_lease` owner/expiry and `reclaim_count` | `CMP-SO-CLAIM-LEASE` | worker loop, RETRY-CONTROLLER, METRICS-FACADE | CLAIM-LEASE only through conditional update | unclaimed → leased → expired/reclaimed → leased or terminal | One active lease per task; reclaim does not increment attempts | Same ST-001 privacy and retention; operational lease data not externally published | `ST-001`, `ICT-001`, L1 `LCD-002` |
| `L2-ST-001-RETRY` | `attempts`, `failure_reason`, `retry_record.first_failure`, `retry_record.second_failure` | `CMP-SO-RETRY-CONTROLLER` | TERMINAL-COMMIT, METRICS-FACADE, worker loop | RETRY-CONTROLLER; terminal child commits final values | first failure → retry attempt or terminal failure | `attempt_no` idempotency and one retry budget | Real error kind/timestamps only; no material contents or student identifiers in logs | `ST-001`, `FR-012`, `DF-2`, `ICT-006` |
| `L2-ST-002-RESULT` | `original_grade`, five rationales, teacher suggestions, scored_at, missing-material impact, prompt/rubric versions, model metadata | `CMP-SO-TERMINAL-COMMIT` | CMP-RESULT-PUBLISHER, METRICS-FACADE, inherited downstream consumers via CT-005 | TERMINAL-COMMIT once for scored outcome | absent → written once → immutable | Same terminal transaction as ST-001 terminal transition and ST-003 insertion | Teacher-only marking inherited; material content is not stored as this state; encrypted/local-region | `ST-002`, `D-AC-REQ-008-01`, `CT-005` |
| `L2-ST-003-OUTBOX-COORD` | Terminal CT-005 payload handoff reference and transaction context | `EXTERNAL-CMP-RESULT-PUBLISHER` (coordination-only; not a child) | inherited Outbox dispatcher, MOD-02, MOD-05 | CMP-RESULT-PUBLISHER | pending → dispatched under inherited infrastructure | Same transaction as ST-001/ST-002; unique by `submission_id + outcome` | Parent Outbox retention and delivery rules; no new retention path | `ST-003`, `ICT-007`, `KD-002` |

## 2. Storage intent and ownership rules

- Use the parent’s single relational task table plus Outbox arrangement. The concrete database product and physical index definitions are deferred to the next level.
- The child split is logical ownership inside the selected component; it does not create separate tables, databases, services, or deployment units unless a later parent-approved design says so.
- `ST-001` updates for status, attempts, failure records, and lease fields use the parent’s atomic-update model. `ST-002` is inserted once at scored terminal completion. `ST-003` is inserted through inherited ICT-007 in the same transaction.
- All state remains inside the inherited local-region and encrypted storage boundary. Student identifiers and material content are not sent to CT-010 and are not added to observability payloads.

## 3. Important data flows

### 3.1 Ingestion and claim

1. CT-004 arrives from MOD-02.
2. `CMP-SO-TASK-INGRESS` performs `submission_id` uniqueness handling and writes the initial ST-001 task before acknowledgement.
3. `CMP-SO-CLAIM-LEASE` conditionally transitions a pending/expired task to `in_progress`, writes the lease, and returns the task payload to the worker.

### 3.2 Assessment completion and failure

- Success: the engine returns validated fields through ICT-005; `CMP-SO-TERMINAL-COMMIT` writes terminal ST-001, immutable ST-002, and the inherited Outbox row atomically.
- Classified failure: `CMP-SO-RETRY-CONTROLLER` writes first/second failure data and either re-enters the attempt within the bounded retry rule or invokes terminal failure commit. No grade is written on failure.
- Worker crash: lease expiry reopens the same attempt and increments `reclaim_count`; it does not create a second task or consume the classified retry budget.

### 3.3 Terminal transition guard matrix

The following matrix makes the terminal child’s preconditions, writes, rejection behavior, and observable side effects explicit. Local guard context (`task_id`, `submission_id`, and `lease_token`) is correlation data around the inherited `ICT-005`/`ICT-006` contracts; it does not change those parent contracts.

| Current state / trigger | Required guards | Successful state writes | Rejection or failure branch | Observable side effect |
|---|---|---|---|---|
| `in_progress` + valid `ICT-005` | Same task identity; current `attempt_no`; active lease token; no existing terminal result | `ST-001.status=scored` + `ST-002` + `ST-003(outcome=scored)` in one transaction | Any write failure maps to inherited transaction-failure handling and rolls back all three writes | `OutcomeCommitted(outcome=scored)` with correlation ID, attempt, duration |
| `in_progress` + `ICT-006`, attempt 1 | Error kind is in the inherited taxonomy; current task/attempt/lease match | Record `first_failure`; advance to attempt 2; no terminal Outbox row | Duplicate attempt callback is ignored/rejected without consuming another retry | `RetryEntered` with error kind, attempt, and retry count |
| `in_progress` + `ICT-006`, attempt 2 or crash-loop cap | Complete retry record; current task identity; terminal lease/attempt guard | `ST-001.status=scoring_failed` + failure fields + `ST-003(outcome=scoring_failed)` in one transaction; no `ST-002` grade | Any write failure rolls back terminal writes and uses inherited `TRANSACTION_FAILED` semantics | `OutcomeCommitted(outcome=scoring_failed)` with failure kind and retry/reclaim counts |
| Any state + stale, mismatched, duplicate, or invalid terminal callback | Current state is not `in_progress`, task/attempt/lease mismatch, terminal result already exists, or callback schema invalid | None | Reject as `STALE_TERMINAL_CALLBACK`, `DUPLICATE_TERMINAL_CALLBACK`, or inherited `INVALID_RESPONSE_SCHEMA`; do not retry in the terminal child | `TerminalCallbackRejected` with reason and correlation ID; no business-state mutation |
| `in_progress` + lease expiry before callback | Lease is expired and no terminal commit has acquired the row | Reclaim through `CMP-SO-CLAIM-LEASE`; preserve `attempt_no`, increment `reclaim_count` | A late callback from the expired lease is rejected by the stale-callback guard | `LeaseReclaimed` and, for the late callback, `TerminalCallbackRejected` |

### 3.4 Metrics read

`CMP-SO-METRICS-FACADE` reads the source timestamps, outcomes, backlog, failure and retry fields from ST-001/ST-002. It returns the inherited ICT-008 shape to `CMP-SCORING-METRICS` and has no write side effect.

## 4. Invariants, consistency, idempotency, and concurrency

| Rule | Enforcement point |
|---|---|
| One task per `submission_id` | TASK-INGRESS uniqueness/duplicate handling |
| One active worker per task | CLAIM-LEASE conditional claim and lease expiry |
| Crash reclaim does not spend business retry | CLAIM-LEASE preserves `attempt_no`; only RETRY-CONTROLLER changes it |
| At most one classified retry | RETRY-CONTROLLER accepts only attempt 1 → attempt 2 |
| Terminal commit requires an active task and lease | TERMINAL-COMMIT accepts only `in_progress` with matching task, attempt, and active lease |
| Terminal state is irreversible | TERMINAL-COMMIT rejects stale, mismatched, and duplicate terminal callbacks |
| Invalid terminal payload does not mutate state | Callback adapter rejects inherited `INVALID_RESPONSE_SCHEMA` before terminal writes |
| Result and event are consistent | TERMINAL-COMMIT owns one local transaction; publisher participates for ICT-007 and cannot commit independently |
| Terminal transaction is all-or-nothing | Any ST-001, ST-002, or ST-003 failure rolls back the complete terminal transaction |
| CT-005 does not duplicate terminal meaning | Unique `submission_id + outcome` and terminal idempotency |
| Metrics cannot affect scoring | METRICS-FACADE is read-only and has no write dependency |

## 5. Ownership confirmation

Parent and sibling ownership was not reassigned. MOD-02 still owns Submission/material state; MOD-05 still owns presentation/notification state; `CMP-RESULT-PUBLISHER` still owns ST-003 write protocol; the selected L1 node remains the owner of ST-001/ST-002. `Q-001` is not solved locally.
