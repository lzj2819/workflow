# Leaf Gate v2 pressure scenarios

| Scenario | Required result |
|---|---|
| First-pass complete Mocktest PASS; no decomposition signal | `STOP_LAYERING` → `VIBECODE` |
| First-pass PASS; Architecture has two explicit children | `CONTINUE_LAYERING` with exact child projections |
| Mocktest `WARNING`, `FAIL`, or `BLOCKED` | `RETURN_TO_ARCHITECTURE`; no Leaf decision |
| Mocktest execution/audit/publication error | `RETURN_TO_VALIDATION`; no Leaf decision |
| Repaired run omits a previously affected testcase | invalid repair chain; no Leaf decision |
| Repaired run still points to old Architecture bytes | stale repair chain; no Leaf decision |
| Current Mocktest hashes old Architecture/Testcases | stale Mocktest; no Leaf decision |
| Full-suite coverage is incomplete | invalid coverage; no Leaf decision |
| Complexity triggers decomposition but Architecture has fewer than two child nodes | `DECOMPOSITION_PLAN_REQUIRED` |
| Decomposition is required at maximum depth | `MAX_DEPTH_REACHED` |
| Semantic judgement fails a criterion but child plan is absent | `DECOMPOSITION_PLAN_REQUIRED` |
| Same input bytes and policy run twice | all five output files byte-identical |

