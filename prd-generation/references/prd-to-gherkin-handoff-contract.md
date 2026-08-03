# Canonical PRD Handoff Contract

This document defines evidence semantics shared by the Architecture and Gherkin
consumers. It does not duplicate the public field schema. The machine shape is
normatively defined by `../schemas/canonical-prd.schema.json`; cross-reference,
uniqueness and readiness rules are implemented in
`../scripts/prd_flow/canonical.py`.

## 1. Authority and direction

`prd.json` is the only machine-authoritative PRD. `prd.md` is generated from it
as a deterministic, fixed twelve-section read-only view. A consumer must never
edit or parse Markdown and treat the result as a competing canonical model.

The only permitted compatibility exception is Derive migration of an approved
legacy parent Markdown artifact. That parser is fail-closed: ambiguous ownership,
duplicate IDs, unknown references or incomplete projections block the layer.

## 2. Evidence classes

Every normative requirement has exactly one source class:

- `explicit`: directly supported by product-owner/user/source evidence;
- `valid_derivation`: mechanically inherited from an explicit parent obligation
  or approved architecture projection.

`assumption`, `unknown`, `hypothesis`, common sense and model memory are not
normative sources. They may appear only as blocking questions or review findings.

Every requirement and acceptance contract carries non-empty `evidence_refs`.
The validator checks presence and references; the independent reviewer is
responsible for confirming the cited evidence actually supports the claim.

## 3. Requirement semantics

- Functional IDs use `REQ-*`; statistical NFR IDs use `NFR-*`.
- A current normative requirement is `atomic` and independently verifiable.
- `priority` is planning metadata; Must/Should/Could all require complete oracles
  when `release_scope=current`.
- Non-current requirements use `out_of_version` or `not_applicable` and require
  a `scope_reason`.
- A retired requirement ID is never reused. Removed obligations remain explicit
  exclusions so downstream traceability does not silently move.
- Derive preserves the parent ID in `parent_requirement_id` and uses
  `source_kind=valid_derivation`.

## 4. Functional Acceptance Contract

A current functional contract must include:

- stable contract ID and one or more known `verifies` IDs;
- `actor`, `preconditions`, one `trigger`, required `response` values;
- observable pass/fail oracles;
- at least one boundary condition paired with its required response;
- at least one exception condition paired with its required response;
- evidence references.

A boundary name, error label, “works normally”, “handles error”, or “returns the
expected result” is not an oracle. Do not use Given/When/Then syntax here.

## 5. NFR Verification Contract

First classify the obligation:

- A rule that must hold for every applicable event is a deterministic functional
  or governance requirement with a functional contract and failure response.
- A target evaluated over a population/window is an NFR.

A current NFR contract requires `population`, `measurement_start`,
`measurement_end`, `unit`, `threshold`, `exclusions`, `pass_rule`, and
`evidence_refs`. A number or percentile alone is incomplete. The generator may
normalize syntax but may not choose a missing population, interval, aggregation,
threshold or exclusion.

## 6. Oracle Coverage Ledger

The ledger contains exactly one row for every requirement in canonical order:

- `ready`: current and linked to at least one complete, type-compatible contract;
- `blocked`: current but missing an authorized oracle or reference;
- `excluded`: explicitly non-current with a reason.

`ready_for_test_generation=true` requires zero blocked rows, zero blocking
questions and the correct review gate. The ledger is computed from the
requirements/contracts; it is never accepted as a caller-provided assertion.

## 7. Root review gate

Root becomes `PASS/approved` only when:

1. release scope is frozen;
2. all current requirements are atomic;
3. IDs/enums are valid and unique;
4. every current item has a complete type-compatible contract;
5. all references resolve and responses do not conflict;
6. the ledger has zero blocked rows;
7. a separate reviewer passes the semantic review hash with no findings.

The semantic review hash is calculated after canonicalization and excludes
timestamps, readiness flags, review metadata and blocking-question rendering.
Changing business content changes the hash; changing only a generation timestamp
does not. A boolean supplied by the producer is never review evidence.

Any unresolved condition yields `FAIL/draft`, `prd.draft.md` and structured
blocking questions. Changing filenames or readiness metadata cannot clear it.

## 8. Derive inheritance gate

Derive does not repeat Root product discovery or independent review. It must:

1. consume an approved/complete parent;
2. identify a unique direct child from explicit architecture ownership;
3. allocate every parent requirement, contract, metric and exclusion to at least
   one direct child, allowing intentional multiple owners;
4. preserve the normative meaning, release scope, priority and evidence;
5. remap all contract/metric references to real child requirement IDs;
6. require `acceptance-contract-projections.yaml` when a parent contract spans
   multiple child owners;
7. give every child at least one inherited current obligation;
8. stage the complete five-file bundle for every child before changing outputs.

A dependency, support relationship, consumer, input precondition, prose token
overlap or existing child PRD is not ownership evidence. Unknown ownership blocks
the layer; it must never be marked tentative or auto-assigned.

## 9. Consumer profiles

Run the executable profiles before handoff:

```powershell
python scripts/validate_prd.py <prd.json> --consumer architecture
python scripts/validate_prd.py <prd.json> --consumer gherkin
python scripts/validate_prd.py <prd.json> --consumer leaf
```

- Architecture receives the problem, scope, current atomic requirements,
  architecture-input constraints, contracts, metrics and evidence. It must not
  invent product behavior or re-number requirements.
- Gherkin receives the same authoritative requirements/contracts/evidence. It
  may choose test techniques, but may not create business responses. Forbidden
  Gherkin/testcase fields in the PRD fail the profile.
- Leaf reads only after Architecture, Gherkin and Mocktest have produced their
  own matching artifacts. The PRD exposes the existing envelope `1.0` plus
  recursion profile fields, but these are not business payload fields.

Passing a PRD consumer profile proves PRD-side compatibility only. It does not
prove Architecture/Gherkin generation, Mocktest semantics or a full workflow run.

## 10. Downstream recovery

When a downstream quality report identifies a PRD defect, map each finding to
the exact requirement, contract, metric, scope decision or evidence field.
Preserve valid content, resolve only the missing authorized decision, regenerate
the canonical model, recompute hashes and rerun all gates. Never rewrite a frozen
Feature/Gherkin artifact to hide a PRD or Architecture defect.
