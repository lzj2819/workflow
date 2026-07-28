---
name: recursive-architecture-design
description: Use when a user needs to refine one selected module, component, or deeper node from a parent architecture package and a scoped current-level PRD.
---

# Parent-to-Child Architecture Design

## Purpose

Generate one child architecture package by refining one selected parent node. The parent package is a binding contract, not background inspiration. It may be a top-level DDD-to-system package or a previous recursive package.

Use this skill for L0-to-L1 module refinement, L1-to-L2 component refinement, and deeper recursion. Do not use it to create a new top-level system architecture.

## Required inputs

Resolve and display before writing:

- `parent_architecture`;
- `target_node_id`;
- `current_prd`;
- `output_dir`.

`parent_prd` is optional and is read only when the parent package lacks necessary requirement traceability. `mode` is `new`, `revise`, or `migrate`; default to `new`.

Read these references before designing:

- `references/input-contract.md` for inputs, modes, and blocking gaps;
- `references/parent-package-adapter.md` for package detection and selective extraction;
- `references/parent-boundary-rules.md` for inheritance and escalation rules;
- `references/local-refinement-and-mapping.md` for local refinement and C1-C6 mappings;
- `references/local-decision-queue.md` for local decisions and parent return;
- `references/artifact-spec.md` for the output package.

## Read references in this order

These are reference files, not independently runnable sub-skills. Read one, perform its stated action, then continue:

1. Read `input-contract.md`. Resolve inputs, mode, and output safety. Stop if a blocking input gap exists.
2. Read `parent-package-adapter.md`. Detect the parent package and uniquely locate `target_node_id`. Produce the selected-node extraction set; stop on an unsafe match.
3. Read `parent-boundary-rules.md`. Build and classify the parent-boundary snapshot. Stop if the current request crosses that boundary.
4. Read `local-refinement-and-mapping.md`. Allocate the current PRD, refine local semantics, and apply C1-C6.
5. Read `local-decision-queue.md`. Classify discovered choices; create `parent-change-request.md` and stop for `return_to_parent`.
6. Read `artifact-spec.md`. Only after the preceding steps are complete, generate the seven-file package and `child-handoff.md`.

## Execution runbook

Follow this table. Do not merely summarize the parent package; write each named result before moving on.

| Stage | Read | Perform | Write | Continue only when |
|---|---|---|---|---|
| 0. Bind inputs | `input-contract.md` | Resolve mode and paths; check output safety. | Create `architecture-manifest.yaml` with input paths, mode, and `draft` status. | Required inputs exist and output is safe. |
| 1. Select and lock | `parent-package-adapter.md`, `parent-boundary-rules.md` | Detect parent shape; uniquely match target; extract only its boundary. | Add parent package type, `node_match_evidence`, `boundary_fingerprint` to the manifest; start the parent-boundary snapshot in `01-design-context.md`. | Target is unique and its binding state/contracts/constraints are available. |
| 2. Allocate work | `local-refinement-and-mapping.md` | Read current PRD and classify every requirement. | Complete the requirement-allocation table and local drivers in `01-design-context.md`. | No requirement is materially ambiguous or wrongly assigned to a sibling. |
| 3. Design internals | `local-refinement-and-mapping.md` | Refine local semantics; choose children and ownership. | Write child registry and dependency map in `02-architecture-decomposition.md`; write state registry in `03-state-and-data.md`. | Every child has `child_id`, responsibility, exclusions, state, dependencies, and rationale. |
| 4. Realize collaboration | `local-refinement-and-mapping.md` | Map parent flows/contracts to internal collaboration and child-only contracts. | Write inherited-contract realization, internal contracts, and success/failure/lifecycle flows in `04-contracts-and-runtime.md`. | Parent contract meaning and ownership remain unchanged. |
| 5. Decide or return | `local-decision-queue.md` | Classify every unresolved architecture choice. | Write local outcomes in `05-local-decisions.md`; for `return_to_parent`, write `parent-change-request.md`. | No unhandled `decide_now` remains. Stop immediately after a parent-change request. |
| 6. Hand off | `artifact-spec.md` | Check the seven artifacts for completeness and create the next-level entry points. | Complete `child-handoff.md`; change manifest status to `ready_for_human_gate`. | Package is internally consistent and ready for one Human Gate. |

## Workflow

### 0. Resolve mode, package shape, and selected node

Resolve paths and mode. Run the Parent Package Adapter before reading parent details.

Match `target_node_id` exactly in the parent package. Only in `migrate` mode may one user-supplied exact display name substitute for a missing stable ID; record match evidence. Stop for zero or multiple matches, an unsupported parent package, or unsafe output overwrite.

### 1. Lock the selected-node boundary

Build a parent-boundary snapshot with the target's responsibility, exclusions, requirement traces, state/data ownership, contracts, direct boundaries, relevant flows, inherited decisions, technology/deployment constraints, delegation, and unresolved items.

Classify extracted items as `inherited-fixed`, `inherited-refinable`, `delegated`, or `unresolved`. Do not start child decomposition until the snapshot is complete.

### 2. Allocate the current PRD

Classify each current requirement as `inherited`, `allocated`, `local`, or `out-of-scope`. Cite parent requirement, FR, contract, flow, or decision IDs when available. Keep drivers inside the selected node: structure, local state, consistency, interaction, failure handling, and local operational tactics.

### 3. Refine local semantics and decompose

Refine only local aggregates, entities, value objects, invariants, commands, internal events, policies, lifecycle states, and child-node collaboration. Do not repeat top-level strategic DDD, redraw parent boundaries, or design sibling internals.

Choose children by responsibility, state ownership, invariants, lifecycle, change reasons, and interaction. Give every child a stable `child_id`, responsibility, exclusions, owned state, allocated requirements, dependencies, and reason for existence.

### 4. Apply C1-C6 mappings

Use the child mappings:

| Mapping | Result |
|---|---|
| C1 | selected parent node to child nodes |
| C2 | local aggregates/state to ownership and consistency boundaries |
| C3 | parent flows to internal runtime collaboration |
| C4 | inherited contracts to internal realization and child-only contracts |
| C5 | parent external dependencies to delegated Adapter/ACL internals only |
| C6 | local drivers to internal tactics only |

Parent contract identifiers, owners, paths/topics, fields, side effects, dependencies, failure semantics, and versioning are immutable by default. Do not introduce a new parent-level platform, datastore, message bus, deployable unit, or public runtime boundary.

### 5. Decide locally or return to parent

Classify discovered choices as `decide_now`, `defer_to_next_level`, `implementation_detail`, or `return_to_parent`.

For `decide_now`, compare only local alternatives and record the result. For `return_to_parent`, create `parent-change-request.md` with source evidence and stop before authoritative decomposition. Never present a parent-impacting change as local deferral.

### 6. Produce and hand off

Produce the normal seven-file package and end at one Human Gate. `child-handoff.md` must expose exact `child_id` values for the next invocation.

## Output package

```text
architecture/
|-- architecture-manifest.yaml
|-- 01-design-context.md
|-- 02-architecture-decomposition.md
|-- 03-state-and-data.md
|-- 04-contracts-and-runtime.md
|-- 05-local-decisions.md
`-- child-handoff.md
```

Create `parent-change-request.md` only when parent approval is required. Do not silently continue as though the change were accepted.

## Stop conditions

Stop before decomposition when the parent package is unreadable, the selected node is not uniquely matched, binding parent state/contracts/deployment constraints are unavailable, the current PRD changes a parent boundary, output would overwrite an existing package without `revise`, or missing information permits materially different child architectures.

## Non-goals

Do not generate code, tests, fixtures, scaffolding, deployment manifests, implementation tickets, or a standalone validation phase. Do not redesign the top-level system.

## Human commands

```text
[APPROVE]
[REVISE phase-N]
[EXPLAIN decision-id]
[PARENT_CHANGE]
[NEXT child_id]
```

`[NEXT child_id]` starts the next refinement only after the current Human Gate is approved.
