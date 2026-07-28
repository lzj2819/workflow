# C Strict Backend P0 Recovery Task

Owner: C (Mocktest strict and Leaf-gate)
Base branch: `verilayer/a-contract-integration`
Required branch: `fix/mocktest-models-package`

## Scope

Restore the missing `mocktest/src/mock_framework/models/` package from the controlled source exactly, limited to the nine-file manifest recorded in C's restoration evidence. Use per-file SHA-256 comparison; do not rewrite business logic and do not modify Tutor, Architecture, Leaf, Coding, or Artifact Contract files.

## Required evidence

1. Source and restored SHA-256 values for every restored file.
2. Redacted, UTF-8 text logs for the following commands in the frozen environment:

```powershell
$env:PYTHONPATH = 'mocktest/src'
python -c "import mock_framework.models"
python -c "import mock_framework.models.validator"
python mocktest/.agents/skills/validate-arch/main_session_strict_driver.py --help
```

3. A PR from `fix/mocktest-models-package` to `verilayer/a-contract-integration`.

## Gate semantics

Before all three commands exit 0 in the A-frozen environment, strict is `ERROR` with category `tool`; it is not Architecture `FAIL`. No strict audit, Leaf run, Coding run, or end-to-end claim is permitted.

Passing `--help` establishes import/argument-parser readiness only. It does not establish a strict PASS, a strict audit, or an Architecture conclusion.
