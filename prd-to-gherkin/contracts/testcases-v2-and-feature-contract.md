# Canonical Testcases v2 and Feature Contract

## 1. Authority chain

`canonical PRD prd/v3 → testcases.json testcases/v2 → testcases.feature feature/v2 → Mocktest`

- `prd/v3` is the only product-fact source.
- `testcases/v2` is the only derived testcase authority.
- Feature is a byte-deterministic view and must never be parsed back into the authority model.
- `STRUCTURE_PASS` never means Mocktest strict `PASS`.

## 2. Input gate

Generation is allowed only when the PRD is `PASS`, `approved|complete`, `ready_for_test_generation=true`, `oracle_blocked_count=0`, has no blocking questions, and every current atomic requirement has a ready ledger row and complete Acceptance Contract. Missing or ambiguous facts return `GENERATION_BLOCKED`; the compiler never invents actors, triggers, responses, thresholds, status codes, or permissions.

## 3. Fixed bundle

Every successful run writes exactly these files:

1. `testcases.json` — canonical `testcases/v2` authority.
2. `testcases.feature` — deterministic `feature/v2` view.
3. `testcases_manifest.json` — source and artifact hashes plus the exact file allowlist.
4. `validation_report.json` — `STRUCTURE_PASS|STRUCTURE_FAIL` only.
5. `quality_report.md` — deterministic human view; Mocktest strict is always `NOT_RUN` here.

The writer refuses an existing output directory and publishes a new directory by one same-volume rename.

## 4. Canonical bytes and identity

- Encoding: UTF-8 without BOM.
- Unicode: NFC.
- Line ending: LF.
- Terminal newline: exactly one.
- JSON: two-space indentation and declared key order.
- Requirement, evidence and tag lists: unique ASCII ID order.
- Scenario order: `acceptance_contract_id → kind(main,boundary,exception,nfr) → source_index → tc_id`.
- TC ID: `TC-<acceptance_contract_id>-<kind-or-index>`; Scenario ID replaces the `TC-` prefix with `SC-`.
- Hashes cover the exact source/artifact bytes, not reconstructed objects.

## 5. Feature v2 grammar

```gherkin
# artifact_schema_version: testcases/v2
# source_prd_artifact_id: <artifact-id>
# source_prd_sha256: <sha256>
Feature: <project-id> acceptance tests

  # <SC-ID>
  # acceptance_contract_id: <AC-ID>
  @<REQ-ID> @<TC-ID>
  Scenario: [<AC-ID>][<kind>]
    Given <first-given>
    And <additional-given>
    When <single-trigger-or-measurement-window>
    Then <first-oracle>
    And <additional-oracle>
```

Rules:

- English Gherkin keywords only; no `# language:` line.
- No Feature tags, description, `Rule`, `Background`, DocString, DataTable, `Scenario Outline`, or `Examples` in `feature/v2`.
- Each Scenario has ordered 1+ Given, exactly one When, and ordered 1+ Then. Additional Given/Then steps use `And`.
- Tags are one stable line: all `@REQ-*`/`@NFR-*` in ID order, followed by exactly one `@TC-*`.
- AC identity and evidence remain authoritative in JSON; the fixed AC comment is trace-only.
- PRD text is NFC-normalized and internal whitespace becomes one space. No other semantic rewriting is allowed.

`Scenario Outline` is deliberately forbidden because `prd/v3` has no explicit approved tabular-row contract and Mocktest consumes only the first Examples block. A future version may enable it only with a versioned PRD field, reversible table escaping, exactly one Examples block, and real loader tests.

## 6. Deterministic Acceptance Contract mapping

### Functional

- Main: actor + every precondition; one trigger; every response + every observable oracle.
- Boundary: actor + every precondition + one boundary condition; same trigger; paired boundary response.
- Exception: actor + every precondition + one exception condition; same trigger; paired exception response.

### NFR

- Given: population and each exclusion.
- When: measurement start and end as one fixed measurement-window step.
- Then: pass rule, threshold, and unit.

If these required fields are incomplete, contain unresolved markers, or cannot be represented without adding business meaning, generation blocks. NFR generation is a structural acceptance projection; its executability is judged later by Mocktest.

## 7. Removed from the authority path

`Requirement Group`, `Clause`, `FACT`, duplicate `Requirement IR`, frozen baseline, standalone Test Obligation graph, ontology graph, pattern-candidate graph, coverage reachability graph, and scenario composition are not canonical outputs. A future diagnostic may emit them outside the five-file bundle, must label them non-authoritative, and may not alter hashes or generation decisions.
