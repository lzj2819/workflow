# 04 Contracts and Runtime — CMP-SCORING-ORCHESTRATOR

This package realizes inherited contracts inside the five child nodes. It does not add a public API, change a parent contract, or introduce a message bus. Parent contract identifiers, owners, fields, side effects, failures, and versioning are immutable here.

## 1. Inherited contract inventory

| Contract ID | Role / owner | Path or name | Required fields / output | Side effects | Dependencies | Failures / timeout | Version |
|---|---|---|---|---|---|---|---|
| `CT-004` | Consumer; provider MOD-02 | SubmissionReceived via inherited Outbox | `submission_id`, `course_id`, `assignment`, `student_name`, `group_name`, `material_refs[]`, `missing_items[]`, `received_at`, `v=1` | Create scoring task | MOD-02 CT-001 | Persist before acknowledgement; delivery retry inherited | v=1, backward-compatible additions only |
| `CT-005` | Producer; MOD-04 through CMP-RESULT-PUBLISHER | SubmissionScored/ScoringFailed Outbox event to MOD-02/MOD-05 | `submission_id`, `outcome`; scored fields or failure fields conditionally | Submission status/read model/notification downstream effects | ICT-007, inherited Outbox dispatcher | `scoring_failed` expresses business failure; not a transport error | v=1 |
| `CT-010` | External consumer through CMP-MODEL-SERVICE-ACL | HTTPS model assessment API | Input `evaluation_prompt`, minimized `materials`, optional `request_id`; output `grade`, `dimension_rationales[5]`, `suggestions[]` | External model evaluation and minimized material egress | ACL and provider | MODEL_TIMEOUT, MODEL_ERROR, INVALID_RESPONSE_SCHEMA; single call bounded by parent limit | Provider version encapsulated by ACL |

### Parent contract semantics that remain unchanged

- CT-004 is deduplicated by `submission_id`; all payload fields are persisted as task context, with business identifiers never sent through CT-010.
- CT-005 has only `scored` and `scoring_failed` outcomes, conditional fields as defined by the parent, and v=1 semantics.
- CT-010 remains behind the inherited ACL; this node never calls the provider directly and never changes its input minimization or error taxonomy.

## 2. Parent-to-child realization map

| Inherited contract | Realizing child / collaborator | Realization |
|---|---|---|
| `CT-004` | `CMP-SO-TASK-INGRESS` | Consume, deduplicate, write ST-001, then acknowledge through inherited delivery behavior |
| `ICT-001 ClaimScoringTask` | `CMP-SO-CLAIM-LEASE` | Conditional pending/expired-lease claim and lease payload to the worker |
| `ICT-002 ComposeEvaluationPrompt` | Parent support `CMP-RUBRIC-PROMPT-COMPOSER` via engine | Referenced only; not designed in this package |
| `ICT-003 LoadMaterialContents` | MOD-02 material read port via engine | Referenced only; MOD-02 owns the port and contents |
| `ICT-004 InvokeModelAssessment` / `CT-010` | Parent support ACL via engine | Referenced only; no provider or ACL redesign |
| `ICT-005 CompleteAssessment` | `CMP-SO-TERMINAL-COMMIT` | Validate that the callback is for the active task, then commit scored outcome |
| `ICT-006 FailAssessment` | `CMP-SO-RETRY-CONTROLLER` | Record classified failure, apply one retry, or request terminal failure commit |
| `ICT-007 PublishScoringOutcome` / `CT-005` | `CMP-SO-TERMINAL-COMMIT` → `CMP-RESULT-PUBLISHER` | Insert inherited Outbox row inside terminal transaction; publisher owns payload assembly/write protocol |
| `ICT-008 QueryScoringMetrics` | `CMP-SO-METRICS-FACADE` → `CMP-SCORING-METRICS` | Read-only source view from ST-001/ST-002 |

## 3. Child-only contracts

These contracts are scoped to this current node and are not parent public contracts. Records are sorted by stable ID.

| Contract ID | Owner | Consumer | Trigger | Schema | Side effects | Dependencies | Errors / timeout / retry | Idempotency | Compatibility |
|---|---|---|---|---|---|---|---|---|---|
| `CSO-IC-001` | TASK-INGRESS | CLAIM-LEASE | ST-001 task persisted | `task_id`, `submission_id`, `attempt_no=1`, `deadline_at`; duplicate marker | None beyond inherited ST-001 insert | CT-004 uniqueness | `DUPLICATE_SUBMISSION` is a handled no-op; no retry beyond inherited delivery | `submission_id` unique | Internal; may add optional diagnostic fields without changing parent contracts |
| `CSO-IC-002` | CLAIM-LEASE | assessment worker / engine loop | Worker poll or lease expiry | `task_id`, task context, `attempt_no`, lease token, deadline_at; `NO_TASK` | Conditional ST-001 claim and lease write | ST-001 row and inherited DU-3 worker loop | `CLAIM_CONFLICT` → poll again; bounded lease expiry/reclaim | One active lease per task | Internal; preserves ICT-001 shape |
| `CSO-IC-003` | assessment engine callback adapter | TERMINAL-COMMIT | ICT-005 callback | Local guard context: `task_id`, `submission_id`, `attempt_no`, active lease token; inherited ICT-005 result fields; transaction context | None before terminal commit | ICT-005; ST-001 current row and active lease | Current status must be `in_progress`; task/attempt/lease must match; stale or duplicate callback is rejected; invalid result fields use inherited `INVALID_RESPONSE_SCHEMA`; no retry by commit child | Terminal state check, task identity, attempt, and lease match | Internal realization of ICT-005; local guard context does not change parent fields |
| `CSO-IC-004` | assessment engine callback adapter | RETRY-CONTROLLER | ICT-006 callback | `error_kind`, `attempt_no`, timestamp, task/lease reference | None before retry decision | ICT-006 and error taxonomy | Unknown error is treated as classified failure only if parent taxonomy permits; retry bounded to one | `task_id + attempt_no` | Internal realization of ICT-006 |
| `CSO-IC-005` | RETRY-CONTROLLER | TERMINAL-COMMIT | Second classified failure or crash-loop cap | `task_id`, `submission_id`, `failure_reason`, complete `retry_record`, terminal reason, transaction context | Requests terminal ST-001/ST-003 commit without creating ST-002 grade | ST-001 retry slice and inherited ICT-007 | Current task must be `in_progress`; `TERMINAL_COMMIT_FAILED` is a local diagnostic classification mapped to inherited `TRANSACTION_FAILED`; all terminal writes roll back | Terminal transition once; no grade on failure | Internal; no CT-005 field change |
| `CSO-IC-006` | METRICS-FACADE | CMP-SCORING-METRICS | ICT-008 query | `task_count`, latency distribution, terminal distribution, backlog, failure_rate, retry_rate | None; read-only | ST-001/ST-002 | `METRICS_QUERY_FAILED` is isolated from scoring path | Naturally idempotent read | Must continue matching parent SM-002/SM-003 source semantics |

## 4. Runtime flows

### 4.1 Success flow

```mermaid
sequenceDiagram
    participant M2 as MOD-02
    participant IN as TASK-INGRESS
    participant CL as CLAIM-LEASE
    participant ENG as CMP-ASSESSMENT-ENGINE
    participant TC as TERMINAL-COMMIT
    participant PUB as CMP-RESULT-PUBLISHER
    M2-->>IN: CT-004 SubmissionReceived
    IN->>IN: deduplicate submission_id; persist ST-001 pending
    CL->>CL: conditional claim; write lease; pending -> in_progress
    CL->>ENG: ICT-001 task payload
    ENG-->>TC: ICT-005 / CSO-IC-003 validated result
    TC->>TC: one transaction: ST-001 scored + ST-002 + ICT-007 context
    TC->>PUB: ICT-007 write CT-005 Outbox row
    PUB-->>M2: CT-005 outcome=scored via inherited dispatcher
```

The transaction is opened and committed by `TERMINAL-COMMIT`. `CMP-RESULT-PUBLISHER` receives the transaction context and inserts `ST-003` within that transaction; it must not commit the Outbox row independently. If the `ST-001`, `ST-002`, or `ST-003` operation fails, the complete terminal transaction is rolled back and the inherited `TRANSACTION_FAILED` operational path applies.

### 4.2 Failure and recovery flow

```mermaid
sequenceDiagram
    participant ENG as CMP-ASSESSMENT-ENGINE
    participant RC as RETRY-CONTROLLER
    participant CL as CLAIM-LEASE
    participant TC as TERMINAL-COMMIT
    ENG-->>RC: ICT-006 attempt 1, classified error
    RC->>RC: record first_failure; apply bounded retry once
    CL->>ENG: second attempt via ICT-001
    ENG-->>RC: ICT-006 attempt 2, classified error
    RC->>TC: CSO-IC-005 complete retry_record and failure reason
    TC->>TC: one transaction: ST-001 scoring_failed + CT-005 Outbox
    Note over CL,RC: Worker crash before classified result: lease expiry reclaims same attempt; attempts does not increment
```

`TERMINAL-COMMIT` accepts the failure request only for the current `in_progress` task and matching attempt/lease context. A late callback, duplicate callback, terminal task, or invalid callback is rejected without changing ST-001, ST-002, or ST-003.

### 4.3 Lifecycle and metrics flow

```mermaid
sequenceDiagram
    participant W1 as worker#1
    participant CL as CLAIM-LEASE
    participant W2 as worker#2
    participant MF as METRICS-FACADE
    participant MET as CMP-SCORING-METRICS
    W1->>CL: claim task; lease active
    W1--xCL: crash before callback
    CL->>CL: lease expiry; reclaim_count + 1; same attempt
    W2->>CL: reclaim task and continue
    MET->>MF: ICT-008 query
    MF-->>MET: source metrics from ST-001/ST-002
```

## 5. Error, retry, timeout, observability, and compatibility

- Classified errors are `MODEL_TIMEOUT`, `MODEL_ERROR`, `INVALID_RESPONSE_SCHEMA`, `MATERIAL_UNREADABLE`, and `PROMPT_ASSEMBLY_FAILED` as inherited. The retry controller does not broaden the public error contract.
- `attempt_no=1` records the first failure and initiates the only retry; `attempt_no=2` terminalizes. A worker crash is a lease/reclaim path and does not spend this budget. `reclaim_count > 3` follows the inherited crash-loop terminal rule.
- CT-010 single-call timeout and the task `deadline_at` remain parent constraints. Deadline tracking does not hard-kill work or fabricate a failure outcome.
- Metrics and logs contain identifiers needed for correlation, timestamps, duration, error kind, request ID, and retry/lease counts only. Terminal paths emit `OutcomeCommitted`, `RetryEntered`, `LeaseReclaimed`, and `TerminalCallbackRejected` observations. They do not contain material content, student names, or business identifiers sent to the provider.
- `STALE_TERMINAL_CALLBACK`, `DUPLICATE_TERMINAL_CALLBACK`, and `TERMINAL_COMMIT_FAILED` are local diagnostic branches only. Parent-facing errors remain `INVALID_RESPONSE_SCHEMA` for invalid assessment data and `TRANSACTION_FAILED` for inherited ICT-007 transaction failure semantics.
- Parent compatibility is preserved: no renamed contract, new required field, weakened failure semantics, moved owner, or version bump.
