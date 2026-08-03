# PRD-to-Gherkin

Deterministic compiler from canonical PRD v3 to canonical testcases v2 and a fixed Gherkin Feature.

## Generate

```powershell
cd prd-to-gherkin
npm.cmd install --ignore-scripts
node scripts/run_gherkin_flow.mjs --prd <canonical-prd.json> --out <new-bundle-dir>
node scripts/validate_bundle.mjs --bundle <bundle-dir>
```

Successful output always contains exactly:

- `testcases.json`
- `testcases.feature`
- `testcases_manifest.json`
- `validation_report.json`
- `quality_report.md`

Read [SKILL.md](SKILL.md) for workflow rules and [contracts/testcases-v2-and-feature-contract.md](contracts/testcases-v2-and-feature-contract.md) for the normative format. `STRUCTURE_PASS` is a handoff result, not Mocktest strict `PASS`.

## Test

```powershell
npm.cmd test
```

The real sibling Mocktest loader contract can be run in an environment containing Mocktest dependencies:

```powershell
python tests/mocktest_loader_contract.py <bundle-dir>/testcases.feature
```
