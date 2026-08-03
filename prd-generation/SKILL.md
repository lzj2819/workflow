---
name: prd-generation
description: Use when the user asks to create a top-level PRD or deterministically derive child PRDs from an approved parent PRD and architecture ownership package.
---

# PRD Generation

## Purpose

Produce an evidence-preserving PRD bundle for Architecture and Gherkin. The
workflow is an upstream contract compiler, not a free-form Markdown writer.

It owns product scope, stable atomic requirements, business oracles, NFR
measurement contracts, exclusions, traceability and readiness. It does not own
architecture design, test-case design, Gherkin, Mocktest, Leaf decisions, code,
integration, or the root orchestrator's `module-result.json` receipt.

Never add `Feature`, `Scenario`, `Given`, `When`, `Then`, testcases, or invented
business responses to a PRD.

## Normative Authority

Read these before generation or maintenance, in this order:

1. `schemas/canonical-prd.schema.json` — public machine shape (`prd/v3`).
2. `scripts/prd_flow/canonical.py` — normalization, semantic validation and
   deterministic rendering rules that JSON Schema cannot express.
3. `references/prd-to-gherkin-handoff-contract.md` — evidence and handoff
   semantics.

`scripts/prd_flow/templates/prd_template.md` is a human-readable outline, not a
second schema. `prd_fillable_template.md` is an input worksheet, not an output
template. If prose conflicts with the schema/validator, the executable contract
is authoritative and the prose must be corrected.

## One Public Model

Legacy `P1`…`P6` dictionaries are internal collection state only. Every public
file is produced from one `CanonicalPrd` model:

```text
evidence input → Root/Derive producer → CanonicalPrd
  ├─ prd.json       machine authority
  ├─ prd.md         deterministic read-only view
  ├─ prd_manifest.json
  ├─ validation_report.json
  └─ execution_log.json
```

Do not serialize `P1`…`P6`, flattened aliases, or a second requirements model.
Do not parse generated Markdown back into authoritative data except inside the
explicit legacy migration/Derive compatibility boundary.

The shared workflow envelope remains `schema_version: "1.0"`. PRD content uses
`artifact_schema_version: "prd/v3"`; never overload one version field with both
meanings. Envelope `status` is `PASS|FAIL|ERROR`; lifecycle `prd_status` is
`draft|approved|complete`.

## Modes

| Inputs | Mode | Rule |
|---|---|---|
| New product or feature | Root | Evidence elicitation plus independent review |
| Approved `parent_prd` + architecture package + target module | Derive | Deterministic inheritance only |

If the request is ambiguous, ask whether this is a top-level PRD or a derived
module PRD. Do not infer Derive ownership from a dependency, consumer,
precondition, prose similarity, or an existing child output.

## Root Workflow

1. **Bind identity and release**: product, release, run/project/node IDs, depth,
   current boundary, non-goals, dependencies and data availability.
2. **Freeze scope**: every candidate is `current`, `out_of_version`, or
   `not_applicable`; non-current items require `scope_reason`.
3. **Atomize**: immutable `REQ-*` / `NFR-*` IDs, one independently verifiable
   obligation per current item. Never reuse a retired ID.
4. **Close oracles**: current functional requirements need complete functional
   Acceptance Contracts; statistical NFRs need full measurement contracts.
5. **Validate**: unique IDs, enums, evidence, references, contract type,
   ledger closure, forbidden test/Gherkin fields and consumer profiles.
6. **Independent review**: bind the reviewer to the semantic hash produced
   after canonicalization but excluding timestamps/readiness/review metadata.
7. **Emit atomically**: `PASS/approved` only after zero blockers and a passed
   independent review; otherwise emit `FAIL/draft` plus blocking questions.

The only mandatory human decisions are release scope, missing business
oracles/NFR measurement definitions, Derive split-contract projections and the
independent Root review. Heuristic SMART/ambiguity suggestions are diagnostics,
not authority and cannot be accepted to bypass a missing oracle.

## Derive Workflow

Derive is fail-closed and does not ask content questions.

1. Reject draft or non-ready parents.
2. Read the architecture package only to enumerate direct children, ownership,
   interfaces and approved projections.
3. Allocate every parent requirement, contract, metric and exclusion across the
   direct-child layer; the union must equal the parent set.
4. Preserve release scope, priority, evidence and behavior. Normalize
   `source_kind` to `valid_derivation` and record the parent ID.
5. When a parent contract spans multiple owners, require
   `acceptance-contract-projections.yaml` with `shared` or a complete `project`
   contract. Never guess a slice.
6. Generate deterministic child IDs and complete bundles. Any missing owner,
   unknown reference, invalid projection, empty child or missing bundle file
   fails the whole layer before existing outputs are changed.

Architecture prose may not create product requirements. Remove no parent
obligation merely because ownership is unclear; return a blocking allocation
report instead.

## Stable Output Format

Every Root and Derive Markdown view has exactly these top-level sections in
this order, even when a section contains `None`:

1. Problem Statement
2. Scope and Non-goals
3. Current Release — Functional Requirements
4. Current Release — Non-functional Requirements
5. Architecture Input Contract
6. Success Metrics
7. Acceptance Contracts
8. Oracle Coverage Ledger
9. Future Backlog / Documented Exclusions
10. Risks, Dependencies, and Blocking Questions
11. Traceability Index
12. Review Report

Record fields, enum values and default types are fixed by the schema. Arrays
are sorted deterministically by stable ID where order has no business meaning.
Missing optional strings use `null`; missing collections use `[]`; missing
booleans/numbers use explicit `false`/`0`, never field omission.

The top-level Leaf consumer profile carries `depth`, `max_depth`,
`node_history`, and the requirement-ID projection because the current formal
Leaf contract requires them. These are workflow profile fields, not PRD payload
semantics.

## Commands

```powershell
# Root, interactive
python scripts/run_prd_flow.py

# Root, reproducible
python scripts/run_prd_flow.py --input root.json --output-dir artifacts/run-1/root `
  --run-id run-1 --project-id demo --node-id root `
  --created-at 2026-08-02T00:00:00Z --review-artifact review.json

# Derive one child
python scripts/run_prd_flow.py --parent-prd parent/prd.md `
  --architecture-package architecture --target-module ModuleA --output child/prd.md

# Derive a complete direct-child layer
python scripts/run_prd_flow.py --derive-all --parent-prd parent/prd.md `
  --architecture-package architecture --output-dir artifacts/run-1

# Validate the canonical artifact or one immediate consumer profile
python scripts/validate_prd.py artifacts/run-1/root/prd.json --consumer canonical
python scripts/validate_prd.py artifacts/run-1/root/prd.json --consumer architecture
python scripts/validate_prd.py artifacts/run-1/root/prd.json --consumer gherkin
python scripts/validate_prd.py artifacts/run-1/root/prd.json --consumer leaf
```

Root review artifacts require `input_hash`, `reviewer`, `reviewed_at`, `status`
and `findings`; `status` must be `passed` and findings empty. A caller-provided
`agent_review_passed` boolean is ignored.

## Terminal States and Exits

| Result | Markdown | Envelope/lifecycle | Handoff |
|---|---|---|---|
| Root blocked | `prd.draft.md` | `FAIL` / `draft` | prohibited |
| Root ready | `prd.md` | `PASS` / `approved` | allowed |
| Derive ready | `prd.md` | `PASS` / `complete` | allowed |
| Derive invalid | no new child bundle | nonzero exit | prohibited |

Exit codes: `0` ready; `1` input error; `2` quality/handoff block; `3`
dependency/configuration; `4` runtime; `5` schema/contract incompatibility.

## Required Verification After Changes

```powershell
python -m compileall -q scripts
python -m unittest discover -s tests -v
python scripts/run_prd_flow.py --help
python scripts/validate_prd.py <prd.json> --consumer canonical
```

The test suite must cover different-content/same-shape output, fixed headings,
byte stability under input reordering, mutation rejection, Root/Derive
round-trip, complete bundle delivery, draft denial and real consumer-profile
compatibility. Do not claim full downstream workflow execution from PRD tests
alone.
