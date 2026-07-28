# C strict backend decision — Day 1

Status: blocked for strict execution; no architecture conclusion was attempted.

## Baseline evidence

The complete command output is retained under `vibe coding/docs/proposals/evidence/day1/`.

| Check | Command outcome | Classification |
|---|---|---|
| Root orchestrator baseline | `27 passed` when run from `vibe coding/` | runnable baseline |
| Root orchestrator baseline from workspace parent | exit `2`; `ModuleNotFoundError: vibecode` | invocation environment error, superseded by the runnable command above |
| Mocktest preflight | exit `0`; resolved `E:\\anaconda\\ANACONDA\\python.exe` and the local strict driver | preflight only |
| Strict driver `--help` | exit `1`; import fails at `mock_framework.models` | tool/package error |
| Leaf-gate `--help` | exit `0` | CLI runnable |

The preflight is not a strict-backend readiness proof: it checks the package root and four third-party imports, but it does not import the driver dependency graph. The driver fails before argument parsing, so no strict run, component hop, validator, strict audit, or architecture result exists.

## Day 2 backend decision

The intended backend remains the repository-local canonical current-session driver:

```powershell
$py = 'E:\\anaconda\\ANACONDA\\python.exe'
& $py mocktest\\.agents\\skills\\validate-arch\\main_session_strict_driver.py <command> --output-dir <run-scoped-dir>
```

`run-strict` is not an acceptable fallback while this import failure remains: it depends on the same Mocktest protocol and would additionally require a local `codex` executable. Do not replace strict execution with prepared Tutor artifacts or an ad-hoc report.

## Actual blocker and recovery gate

`mocktest/src/mock_framework/models/` is absent, while
`mock_framework/improvement/arch_modifier.py` imports
`mock_framework.models.validator`. This is a tool/package completeness defect, not an Architecture defect.

Day 2 is blocked until the authoritative Mocktest package revision supplies the missing `mock_framework.models` dependency (or its compatible replacement) and the exact command below succeeds:

```powershell
& $py mocktest\\.agents\\skills\\validate-arch\\main_session_strict_driver.py --help
```

After that gate, run a fresh `init` against a B-provided Architecture/Testcases pair in a unique work directory, then confirm that its `strict_audit.json` and formal delivery files can be produced. Network/model availability is not yet tested; canonical orchestration will need the current Codex session to supply each raw component/validator JSON response after initialization.

## Result semantics (normative for C handoffs)

| Dimension | Source of truth | Meaning | Downstream effect |
|---|---|---|---|
| Strict execution completeness | `strict_audit.json.status == PASS` plus complete component/validator evidence | The requested strict procedure completed audibly | Necessary, never sufficient, for Leaf |
| Architecture conclusion | formal `mocktest_report.status` / `validation_status` | `PASS` or completed `FAIL` for the architecture | Only `PASS` may reach Leaf |
| Tool or environment error | formal `status=ERROR`, incomplete audit, import/process/configuration failure | No valid architecture conclusion | Block Leaf and Coding; count separately |

In particular, `CMP-CONFIG-STORE` is the planned strict negative calibration: a completed audit together with architecture `FAIL` is a valid result and must block Leaf and Coding.
