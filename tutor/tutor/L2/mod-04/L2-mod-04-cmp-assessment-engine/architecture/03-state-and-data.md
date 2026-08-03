# 03 State and Data — CMP-ASSESSMENT-ENGINE

## 1. State ownership registry (sorted)

| state_id | state | owner child ID | readers | writers | lifecycle | consistency boundary | retention/privacy | parent trace |
|---|---|---|---|---|---|---|---|---|
| `AE-STATE-001` | `EvaluationContext` | `CMP-AE-EVALUATION-COORDINATOR` | coordinator, validator, assembler, classifier | coordinator | created at attempt start; discarded after `ICT-005`/`ICT-006` callback or crash | one assessment attempt in one worker process | no durable retention; logs contain identifiers only | `ICT-001`, `ICT-002`, `ICT-003`, `ICT-004` |
| `AE-STATE-002` | `ModelAssessmentResponse` | `CMP-AE-RESPONSE-VALIDATOR` | validator, assembler | coordinator hands off; validator normalizes | exists only during validation and assembly | response validation boundary | do not persist raw material or student identifiers | `ICT-004`, `FR-008` |
| `AE-STATE-003` | `ValidatedAssessmentPayload` | `CMP-AE-RESULT-ASSEMBLER` | coordinator and orchestrator callback | assembler | created only after validation; discarded after `ICT-005` handoff | scored-result payload boundary before parent transaction | version and result metadata may be persisted by parent; local copy is transient | `ICT-005`, `D-AC-REQ-008-01`, `LCD-003` |
| `AE-STATE-004` | `EvaluationFailure` | `CMP-AE-OUTCOME-CLASSIFIER` | coordinator and orchestrator callback | classifier | created on local failure; discarded after `ICT-006` handoff | failure-reporting boundary | error kind and timing only; no material content | `ICT-006`, `DF-2` |

### Inherited state ownership (not reassigned)

| Parent state | Owner | L2 relationship |
|---|---|---|
| `ST-001 ScoringTask` | `CMP-SCORING-ORCHESTRATOR` | read through execution context; no local write |
| `ST-002 AssessmentResult` | `CMP-SCORING-ORCHESTRATOR` | L2 supplies validated content; parent writes it in terminal transaction |
| `ST-003 Outbox` | `CMP-RESULT-PUBLISHER` inside parent terminal transaction | L2 never writes or publishes CT-005 |
| `ST-004 RubricPolicy` | `CMP-RUBRIC-PROMPT-COMPOSER` | L2 receives versioned prompt output; no local ownership |

## 2. Storage intent

There is no L2-owned database, cache, object store, event store, or queue. Local state is in-process and attempt-scoped. The parent remains responsible for the database transaction, shared material storage, Outbox, backup, encryption, and deployment behavior described by `KD-002` and `KD-003`.

## 3. Data flows

### Successful evaluation

1. The orchestrator supplies task context and `attempt_no` to the coordinator.
2. The coordinator sends assignment/material references/missing items to `ICT-002` and stores only returned prompt and version metadata in `AE-STATE-001`.
3. The coordinator reads material contents through `ICT-003`; ownership remains MOD-02.
4. The coordinator calls `ICT-004`; the validator checks the response and produces `AE-STATE-002`.
5. The assembler creates `AE-STATE-003` and reports it through `ICT-005`; the orchestrator persists `ST-002` and completes the parent transaction.

### Failure and recovery

Prompt assembly failure, unreadable material, model timeout/error, or invalid response is normalized into `AE-STATE-004` and reported through `ICT-006`. The orchestrator alone decides the one retry, backoff, terminal `scoring_failed`, `retry_record`, and Outbox write. A worker crash leaves no L2 durable state; lease recovery causes the parent to rerun the attempt.

## 4. Invariants, consistency, idempotency, and concurrency

- A validator failure cannot be converted into a scored result or fallback grade.
- Exactly five dimension rationales are required; duplicate or missing dimensions fail validation.
- `missing_items[]` does not itself fail the assessment; it must be reflected in the prompt/result impact explanation.
- The child is re-entrant for an attempt. It must not assume a prior in-memory context survives worker crash.
- `ICT-005` and `ICT-006` callbacks are parent-controlled and idempotent by the parent terminal/attempt rules; the child does not add a competing deduplication store.
- Each model attempt uses the parent-provided request correlation and ACL semantics; retry attempts use a new request id as already defined by `ICT-004`.
- Logs and metrics use task/request identifiers, durations, error kinds, and versions only; raw material and student/business identifiers are not emitted to the model or logs.

## 5. Ownership confirmation

No parent or sibling state ownership was reassigned. No local state is retained after the attempt, and no new consistency boundary crosses `MOD-04`.
