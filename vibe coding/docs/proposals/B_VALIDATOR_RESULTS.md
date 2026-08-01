# B Day 1 validator record

Status: contract-fixture validation only. These are not production Adapter runs or benchmark evidence.

> Scope note (A review, Day 1): the adapter contract tests (`tests/integration/test_architecture_adapter.py`, `test_gherkin_adapter.py`) and the Day 2 adapter draft were split out of the Day 1 PR per A's review. The `6 xfailed` records below refer to the pre-split branch state; those tests are preserved for Day 2 and are no longer part of this branch.

## Root orchestrator baseline

| Command | Exit | Result |
|---|---:|---|
| `python -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py` (working directory: `vibe coding`; interpreter recorded per rerun below) | 0 | 27 passed in 4.87s |

## Inputs

Hashes below are SHA-256 over LF-normalized file bytes (CR stripped per line). Raw working-tree hashes differ on checkouts with CRLF line endings; the normalized form is the stable, cross-checkout identity.

| Input | SHA-256 |
|---|---|
| `vibe coding/tests/fixtures/contracts/architecture.example.json` | `6944309b23227436e8a929df1eed2b32ae8c4df9766919187ff0c50c455ca93c` |
| `vibe coding/tests/fixtures/contracts/testcases.example.json` | `ad1c79e9bb72f4a87af740f9a694f834e7bdca12f06f7ed55050638649d0fe9c` |
| `vibe coding/tests/fixtures/contracts/s1.feature` | `0a19c3aec005bbafa34a6860496fd5cf72ad3932115d52299fab7132e8465f52` |
| `vibe coding/tests/fixtures/contracts/requirement-model.example.yaml` | `2db65d5a137eef75ba52980e5d8b561646f5605393b0c99286c87f370f8f961b` |

## Validator executions

Output hashes are SHA-256 over UTF-8 normalized stdout (PowerShell line joining followed by a final LF). Stderr was empty for both passing executions.

| Validator command | Exit | stdout SHA-256 | Classification | Summary |
|---|---:|---|---|---|
| `node prd-to-gherkin/scripts/validate_requirement_graph.mjs vibe coding/tests/fixtures/contracts/requirement-model.example.yaml` | 0 | `db60be6520f615cf3f285c4fcc95a13cd0acb173d4b9a4874777a8ebb9bee21e` | `PASS` | 8 nodes, 7 edges, one authoritative Scenario, all five graph coverage rates are 1. |
| `node prd-to-gherkin/scripts/validate_feature.mjs vibe coding/tests/fixtures/contracts/s1.feature vibe coding/tests/fixtures/contracts/requirement-model.example.yaml` | 0 | `21d1ab50b0feeef91e7e839e22ac304589a6892c451369debcd40a6c6f65bb13` | `PASS` | Syntax, YAML/model integrity, and one TC-to-Scenario trace all pass. |

## Recorded setup failure

Before dependency installation, both validators exited 1 with `ERR_MODULE_NOT_FOUND` for `js-yaml`; classification: `TOOL_ENVIRONMENT/DEPENDENCY_MISSING`. An in-sandbox `npm.cmd ci` timed out at 60 seconds and left a partial dependency tree. The locked dependency install was then completed using `npm.cmd ci` (exit 0: 4 packages added, 0 vulnerabilities); validators were rerun successfully.

## Limits

These validators prove structural traceability and graph/Feature conformance only. They do not prove complete PRD interpretation, semantic equivalence of natural-language outcomes, or that the S1 fixture is a production-generated result.

## Day 2 pre-freeze rerun

The unchanged independent S1 inputs were rerun while A's integration branch/profile freeze was unavailable. Both commands exited 0 with the same input and normalized-stdout hashes listed above; classification remains `PASS`. This records validator availability for future Adapter work, not an end-to-end or strict Mocktest result.

The pre-freeze Adapter test design ran as `6 xfailed in 0.32s`; the existing root baseline remained `27 passed in 4.51s`. The xfails are intentional contract gates and must become ordinary passing tests only after A resolves the pending contract decisions.

## Post-freeze rerun (A baseline `4c54853`)

Rerun on branch `verilayer/b-generation` after confirming `4c54853` is an ancestor (`git merge-base --is-ancestor 4c54853 HEAD`, exit 0). No rebase was required; the branch already contains the frozen baseline.

Environment: CPython 3.13.13 (MSC v.1944, 64-bit) on Windows 11; Node.js v24.11.0. Validator dependencies installed via `npm ci` in `prd-to-gherkin/` (exit 0, 0 vulnerabilities) — before install both validators exited 1 with `ERR_MODULE_NOT_FOUND` (`js-yaml`), classification `TOOL_ENVIRONMENT/DEPENDENCY_MISSING`.

| Command (working directory) | Exit | Result |
|---|---:|---|
| `python -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py` (`vibe coding`) | 0 | 27 passed, 15 subtests passed in 3.49s |
| `python -m pytest -q tests/integration/` (`vibe coding`) | 0 | 6 xfailed in 0.18s |
| `node prd-to-gherkin/scripts/validate_requirement_graph.mjs vibe coding/tests/fixtures/contracts/requirement-model.example.yaml` (repo root) | 0 | `PASS`: 8 nodes, 7 edges, 1 authoritative Scenario, all five coverage rates 1 |
| `node prd-to-gherkin/scripts/validate_feature.mjs vibe coding/tests/fixtures/contracts/s1.feature vibe coding/tests/fixtures/contracts/requirement-model.example.yaml` (repo root) | 0 | `deterministic_gate: PASS`, `failed_checks: []` |

Output hashes are SHA-256 over UTF-8 stdout with CR stripped per line (final LF retained):

| Validator | stdout SHA-256 |
|---|---|
| `validate_requirement_graph.mjs` | `db60be6520f615cf3f285c4fcc95a13cd0acb173d4b9a4874777a8ebb9bee21e` (byte-identical to the recorded run) |
| `validate_feature.mjs` | `8481129d603606807d53eeaad958b6b2cc1821e06879b9cc6c0d7c36894b5764` |

The graph-validator output is byte-identical to the recorded run. The feature-validator output hash differs from the recorded `21d1ab50…`; the recorded hash used PowerShell line joining, whose exact byte layout could not be reproduced in this shell, so the fresh hash above was captured with the stated normalization. Both runs agree on classification `PASS` and exit 0; this is a normalization difference, not a content divergence claim.

All four S1 fixture inputs reproduce the LF-normalized input hashes in the Inputs table above (`git diff --check` against the A baseline: exit 0). No strict Mocktest, Leaf-gate, Coding, or model-invocation result is claimed here; the 6 adapter xfails remain intentional contract gates. Gate remains NO-GO pending A's review.
