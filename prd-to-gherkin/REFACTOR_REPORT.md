# PRD-to-Gherkin Refactor Report

## Outcome

The old prompt-and-validator collection is now an executable compiler:

`prd/v3 → testcases/v2 → feature/v2 → fixed five-file bundle`

## Removed unreasonable or redundant design

| Old design | Problem | Resolution |
|---|---|---|
| Reparse original PRD lines into Group/Clause/FACT/IR | Duplicated canonical PRD v3 facts and IDs | Consume PRD v3 JSON directly |
| `requirement-model.yaml` declared authoritative | A second truth source beside PRD; no complete Schema or generator | `testcases.json` is the only derived authority |
| Separate ontology/pattern/coverage graphs | High model count; reachability did not prove semantic fidelity | Removed from authority path and repository core |
| Two validators with incompatible model shapes/statuses | One required semantic/coverage graphs; one required flat FACT/IR/AC/TC lists | One compiler module and one projection validator |
| Default scenario composition | Documentation and validator contradicted each other about component `@TC` tags | Disabled in v2 |
| Optional, under-specified Feature formatting | Title, tag order, Scenario order, step identity, escaping and newline could drift | `feature/v2` freezes every structural choice |
| Generic `PASS` wording | Could be mistaken for strict business validation | Only `STRUCTURE_PASS|STRUCTURE_FAIL`; strict is `NOT_RUN` |
| `[module].feature` and ad hoc reports | Filenames and bundle membership changed per run | Exact five-file allowlist and byte hashes |
| `testcases/v1` proposal | Conflicted with Mocktest's existing normalization envelope | Producer version is `testcases/v2`; Mocktest uses the Feature branch |

## Canonical mapping

- Functional AC: one main Scenario, one Scenario per boundary pair, one per exception pair.
- NFR AC: one Scenario preserving population, exclusions, measurement window, pass rule, threshold and unit.
- Each Scenario: ordered 1+ Given, exactly one When, ordered 1+ Then.
- Each TC: stable TC/SC IDs, AC and requirement references, source kinds, minimal evidence-only obligation, ordered source-field steps.
- Any missing readiness, oracle, evidence, pair, trigger, NFR measurement field or ambiguous marker blocks generation.

## Fixed output format

See `contracts/testcases-v2-and-feature-contract.md` and `schemas/canonical-testcases.schema.json`. The Feature always has three metadata comments, one Feature header, then identical Scenario blocks with fixed comments, tag order, title grammar and step keyword progression. Background, Rule, Outline, Examples, DocString and DataTable are forbidden in v2.

## Verification evidence

- Node contract tests: 7 passed.
- Same PRD, two fresh directories: all five files byte-identical.
- Input reorder: TC identity/content/order unchanged.
- Different content: canonical model keys and Feature block structure unchanged.
- Missing observable oracle: `GENERATION_BLOCKED`.
- Independent Draft 2020-12 Schema meta/instance validation: PASS.
- Official `@cucumber/gherkin` parser: PASS.
- Real sibling Mocktest `GherkinParser`: PASS, 4 scenarios.
- Bundle and compatibility Feature CLIs: `STRUCTURE_PASS`.

Mocktest strict was not run and is not part of the generation bundle.

## Migration

Use `SKILL.md` and `scripts/run_gherkin_flow.mjs`. `skill3.md` remains a compatibility pointer. Old `requirement-model.yaml`, ontology/pattern/coverage/composition inputs and `validate_requirement_graph.mjs` are no longer accepted.
