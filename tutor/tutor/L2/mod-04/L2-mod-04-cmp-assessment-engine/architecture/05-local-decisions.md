# 05 Local Decisions — CMP-ASSESSMENT-ENGINE

## 1. Inherited decisions (binding)

| Decision | Inherited rule | L2 treatment |
|---|---|---|
| `KD-001` | model vendor access is isolated behind ACL; materials are minimized; vendor is replaceable | coordinator uses `ICT-004`; no direct network or vendor client |
| `KD-002` | same-group deployment, task table + Outbox, one relational consistency boundary, shared material storage | no local persistence or messaging; result is handed to parent |
| `KD-003` | basic operations, encryption, backups, monitoring, RPO/RTO, minimal logs | local logs are redacted and correlation-oriented |
| `LCD-003` | prompt/rubric versions are captured for auditability | assembler carries versions into the `ICT-005` payload |
| `LCD-004` | ten minutes is a metric window, not a force-kill rule | no local deadline termination or fake failure |

## 2. Local decision records (sorted)

| Decision ID | Source | Choice | Alternatives considered | Consequences / risks | Classification |
|---|---|---|---|---|---|
| `LCD-AE-001` | `REQ-DD001`, `FR-008`, `ICT-004` | Make `CMP-AE-RESPONSE-VALIDATOR` the sole guard before `ICT-005`; require A–E and exactly five dimension rationales | validate in assembler; trust ACL schema only | centralizes domain invariants and prevents partial scored results; validator rules must remain aligned with rubric dimensions | `decide_now` |
| `LCD-AE-002` | `D-AC-REQ-008-01`, `ICT-003` | Treat `missing_items[]` as an assessable limitation and produce `missing_materials_impact`, while `MATERIAL_UNREADABLE` remains a failure | fail every incomplete submission; ignore missing items | preserves the acceptance boundary and makes limitations auditable; result quality depends on prompt composer/model behavior | `decide_now` |
| `LCD-AE-003` | `ICT-004`, `ICT-006`, `DF-2` | Use `CMP-AE-OUTCOME-CLASSIFIER` to normalize local errors, but delegate retry/terminal choice to the orchestrator | let each child decide retry; map all errors to generic failure | parent state machine stays authoritative; unknown error categories need explicit parent-compatible mapping | `decide_now` |
| `LCD-AE-004` | `KD-001`, `KD-003` | Keep only safe diagnostics in local context/logs: request ID, duration, versions, error kind, attempt number | persist raw prompt/material/response for debugging | reduces privacy and leakage risk; debugging relies on redacted correlation and parent audit records | `decide_now` |

## 3. Delegated decisions for next level

| Decision | Classification | Target | Trigger |
|---|---|---|---|
| `LCD-005` | `defer_to_next_level` | `CMP-RUBRIC-PROMPT-COMPOSER` and `CMP-MODEL-SERVICE-ACL` | when either support component is refined, decide exact prompt text, compression/truncation, vendor adapter details, and safe redaction tactics |
| `LCD-006` | `implementation_detail` | implementation/design detail stage | decide physical table/schema, polling interval, lease values, endpoint configuration, secret configuration, and framework logging wiring |

## 4. Parent-owned decisions prohibited locally

The following are not local decisions: changing CT-004/CT-005/CT-010, adding a public API or event, transferring material/result ownership, adding a deployable unit, selecting a new database/message bus/workflow/cache/search platform, changing the retry count, force-killing tasks at ten minutes, or adding MOD-04 to CT-012 retention deletion without parent approval.

## 5. Decision queue outcomes

| Queue item | Outcome | Reason |
|---|---|---|
| `LCD-AE-001`–`LCD-AE-004` | decided now | each choice remains inside the selected node and is required for a coherent package |
| `LCD-005` | delegated | exact support-component behavior can be refined without changing current parent boundaries |
| `LCD-006` | implementation detail | physical configuration does not alter architecture ownership or contracts |
| `Q-001` | recorded as parent-level unresolved, not `return_to_parent` | current PRD does not depend on retention deletion; no local deletion path is introduced |

No `decide_now` item remains unhandled, and no parent-change request is required.
