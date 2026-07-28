# C defect taxonomy — Day 1

Status: frozen proposal for C evidence classification. It classifies evidence; it does not reinterpret tool errors as architecture defects.

## Classification table

| Category | Decision basis | Normal severity | Traceability required | Tool error? |
|---|---|---|---|---|
| `entry` | no unique/allowed entry component or action for a scenario | FAIL | requirement, scenario, candidate components | no |
| `contract` | absent, incompatible, or unbound provider/consumer contract | FAIL | requirement, scenario, interface, components | no |
| `data_schema` | field/type/nullability/version mismatch across an interface | FAIL | requirement, scenario, interface, field evidence | no |
| `state` | illegal/missing state, transition, persistence, or idempotency behavior | FAIL | requirement, scenario, state/evidence refs | no |
| `flow` | required business sequence, branch, retry, or terminal behavior is unsupported | FAIL | requirement, scenario, hop/flow evidence | no |
| `auth` | authorization, identity, tenancy, or privilege boundary is missing/incorrect | FAIL | requirement, scenario, actor/interface evidence | no |
| `nfr` | measurable latency, availability, capacity, privacy, or reliability requirement lacks evidence/model | WARNING or FAIL when mandatory | requirement, scenario, measurement/model evidence | no |
| `tool` | import, dependency, network/model, invalid agent JSON, audit, file, process, schema, or identity execution fault | ERROR | command/exit/error artifact; no invented business scenario | yes |

Severity is evidence-led: use `ERROR` only for the `tool` category. An architecture finding remains `FAIL` or `WARNING` even when strict execution completed successfully.

## Required evidence fields

Every finding must identify `requirement_ids`, `scenario_ids`, and available `component_ids`/`interface_ids`, state expected versus observed behavior, cite an evidence artifact, and state a severity. A missing traceability link is itself a `tool`/schema error until it can be resolved; it is not grounds to infer an architecture failure.

## Reporting split

```text
strict execution completeness: COMPLETE / INCOMPLETE / NOT_RUN
architecture result:           PASS / FAIL / WARNING / NOT_RUN
tool result:                   NONE / ERROR
```

Aggregate architecture defect counts exclude `tool`. Tool errors remain in execution reliability metrics and preserve their evidence paths, command exit codes, and redacted messages.

## C2 ablation convention

Every C2 control artifact must set all three fields exactly:

```json
{"is_ablation": true, "full_run": false, "status": "ABLATION_NOT_RUN"}
```

It is neither a Mocktest PASS nor a strict execution result, and it must not enter Leaf, Coding, architecture-defect totals, or full-run denominators.

## CMP-CONFIG-STORE negative rule

`CMP-CONFIG-STORE` is a strict negative calibration. If its strict audit is `PASS` while its semantic architecture result is `FAIL`, report execution `COMPLETE`, architecture `FAIL`, tool `NONE`, and `downstream_gate=BLOCK`. Leaf and Coding are prohibited.
