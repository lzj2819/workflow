# B proposal: Testcases, Feature, and requirement-model contract (Day 1)

Status: proposed for A's review; no production Gherkin Adapter is included.

## Audit scope and field gap

The 22 read-only Features all provide scenario comments and `@TC-*` / requirement tags. The 16 historic `testcases.json` files preserve the envelope plus only `testcases[]`, where each item is `id`, `name`, `requirement_ids`, `status`, and assertion prose. They omit Feature provenance, scenario IDs, preconditions, step templates, deterministic expected results, rendering mode, requirement-model graph, oracle evidence, verification state, and error classification. They are prepared migration fixtures rather than production Gherkin output.

## Proposed `testcases.json` profile

The artifact MUST carry A's envelope and the following payload.

| Field | Required | Purpose |
|---|---:|---|
| `features` | yes | Feature records: `feature_id`, `name`, `source_feature_path`, `content_sha256`, `requirement_ids`, and `verification_status`. |
| `scenarios` | yes | Scenario records: `scenario_id`, Feature reference, exactly one testcase ID, Gherkin kind, tags, and requirement IDs. |
| `testcases` | yes | Records with `testcase_id`, `requirement_ids`, `preconditions`, `action`, `expected_result`, `acceptance_criteria_ids`, `verification_status`, `source_feature_path`, and `evidence_ids`. |
| `requirement_model_path` | yes | Repository-relative YAML source of truth for semantic and coverage graphs. |
| `requirement_model_sha256` | yes | SHA-256 of that exact model file. |
| `validation` | yes | Validator command identity, exit code, status, output path/hash, and classified errors. |

`testcase_id` is canonical. Day-2 Adapter input may accept historic `id`, but production output must use `testcase_id` only. `verification_status` is an artifact-local verification state; it does not replace envelope `status`.

## Minimum requirement-model fields

`requirement-model.yaml` is the only semantic source of truth and minimally contains: `baseline` (`status: FROZEN`, eligible requirement IDs), `requirement_groups` and explicit FACT clauses, `requirement_ir`, `acceptance_criteria` with deterministic oracle, `test_conditions` with frozen step templates and render mode, `ir_dispositions`, `semantic_graph`, `coverage_graph`, and `scenario_compositions`. The graph must provide the authoritative SOURCE → REQUIREMENT_GROUP → CLAUSE → FACT → REQUIREMENT_IR → TEST_OBLIGATION → TEST_CONDITION → SCENARIO path.

## Feature rules

An authoritative Feature uses English Gherkin keywords and has one preceding `# SC-*` ID per Scenario, exactly one `@TC-*` tag per atomic Scenario, and root requirement tags compatible with `REQ-<root>-R<n>`. Steps must match the referenced testcase template. `UNKNOWN`, unresolved hypothesis, and localized keyword directives are invalid.

## S1 contract-only example

The fresh fixture quartet is:

- `vibe coding/tests/fixtures/contracts/architecture.example.json`
- `vibe coding/tests/fixtures/contracts/testcases.example.json`
- `vibe coding/tests/fixtures/contracts/s1.feature`
- `vibe coding/tests/fixtures/contracts/requirement-model.example.yaml`

It specifies a deliberately small note-capture boundary and is not copied from Tutor code, tests, or business behavior. It is not a production run or a positive benchmark result.

## Requested A decision

Requested field/change: publish the `testcases.json` profile and its requirement-model link as an artifact profile under the existing v0.1 envelope.

Reason: string assertion lists cannot prove scenario-to-testcase-to-requirement traceability or preserve validator evidence.

Backward compatibility: historic `id` / assertion fixtures can be read as migration input and classified `ADAPTER_NEEDED`; absent deterministic details stay absent and block a production PASS.

Required downstream action: C uses the Feature, model, testcases, and validation evidence; D uses public Feature/testcases, expected results, and source hashes. A owns envelope/status/version changes.
