---
name: prd-to-gherkin
description: Compile an approved canonical PRD v3 into canonical testcases/v2 and a byte-deterministic Gherkin Feature bundle.
---

# PRD to Gherkin

Read [contracts/testcases-v2-and-feature-contract.md](contracts/testcases-v2-and-feature-contract.md) before generating artifacts.

## Required input

One canonical `prd/v3` JSON artifact. Markdown PRDs, original line-number parsing, Requirement Group/FACT/IR graphs, and Architecture documents are not accepted as product-fact inputs.

## Run

```powershell
node scripts/run_gherkin_flow.mjs --prd <canonical-prd.json> --out <new-output-directory>
node scripts/validate_bundle.mjs --bundle <output-directory>
```

Successful generation produces exactly the five contract files. Existing output directories are refused. `GENERATION_BLOCKED` means the PRD must be repaired or explicitly re-approved; do not fill gaps in Gherkin.

## Human gate

Check `validation_report.json` and `quality_report.md`. `STRUCTURE_PASS` authorizes handoff to Mocktest; it is not Mocktest strict `PASS`. Keep the generated Feature frozen during an Architecture-only Mocktest correction loop.

## Compatibility

Mocktest currently consumes `testcases.feature` through its Gherkin branch. Its existing normalization envelope named `testcases/v1` is not this producer schema; do not rename `testcases/v2` to `testcases/v1`.
