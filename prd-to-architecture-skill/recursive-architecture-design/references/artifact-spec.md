# Architecture Artifact Specification

Generate architecture documents only. Do not generate code, tests, scaffolding, deployment manifests, standalone validation reports, or implementation tickets.

A normal package contains exactly these seven files:

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

Create `parent-change-request.md` only when a current requirement must change a parent-owned decision or boundary. Then stop before producing an authoritative full decomposition unless the user explicitly asks for a non-authoritative draft.

## `architecture-manifest.yaml`

Required content:

- current node name, level label, `target_node_id`, responsibility, and exclusions;
- input paths for `current_prd`, `parent_architecture`, optional `parent_prd`, ancestors, and `output_dir`;
- `mode`, `parent_package_type`, parent node identity, and `node_match_evidence`;
- `boundary_fingerprint` with parent artifact, contract, decision, ownership, and deployment references used by this package;
- generated artifact inventory;
- status: `draft`, `blocked_parent_change`, or `ready_for_human_gate`.

## `01-design-context.md`

Required content:

- parent-boundary snapshot: responsibility, exclusions, state, contracts, dependencies, flows, inherited decisions, technology constraints, and deployment boundary;
- requirement allocation table using `inherited`, `allocated`, `local`, and `out-of-scope`;
- current-level drivers limited to the selected node;
- assumptions, open questions, and conflicts that caused a parent-change request.

## `02-architecture-decomposition.md`

Required content:

- local semantic refinement: concepts, aggregates, invariants, commands, internal events, policies, and lifecycle states as applicable;
- child registry. Every child has a stable `child_id`, responsibility, exclusions, owned state, requirement allocation, dependencies, and reason for existence;
- dependency map among child nodes and external parent/sibling boundaries;
- explicit confirmation that siblings are referenced but not redesigned;
- rationale based on responsibility, state, invariants, lifecycle, change reasons, and interaction.

## `03-state-and-data.md`

Required content:

- state ownership registry: state, owner child ID, readers, writers, lifecycle, consistency boundary, retention/privacy constraints, and parent trace;
- storage intent constrained by parent technology decisions;
- data flows for important writes, reads, derived state, and externalized state;
- invariant, consistency, idempotency, and concurrency rules where relevant;
- explicit confirmation that parent and sibling ownership was not reassigned.

## `04-contracts-and-runtime.md`

Required content:

- inherited contract inventory with parent IDs, owner, path/topic/name, fields, side effects, dependencies, failures, and versioning;
- realization map from each inherited contract to current child nodes;
- child-only ports, commands, queries, events, and callbacks with node-scoped identifiers;
- two or three local flows covering success, failure/recovery, and lifecycle behavior;
- architecturally relevant error, retry, timeout, idempotency, observability, and compatibility notes;
- confirmation that inherited external contract semantics are unchanged unless a parent-change request exists.

## `05-local-decisions.md`

Required content:

- local decisions and their alternatives/consequences;
- inherited decision references, clearly marked as inherited;
- delegated decisions for the next level;
- parent-owned decisions prohibited locally;
- local decision-queue outcomes.

## `child-handoff.md`

Required content:

- current node identity, responsibility, exclusions, parent binding, and boundary fingerprint;
- child registry with exact `child_id` values usable as the next `target_node_id`;
- inherited and child-only contract registries;
- state ownership registry;
- inherited, local, delegated decisions and unresolved risks;
- recommended next child targets and required ancestor context, if any.

## `parent-change-request.md`

Required content:

- triggering requirement or human constraint;
- exact parent artifact, source ID, contract, ownership, dependency, ADR, technology choice, or deployment boundary affected;
- current inherited rule and proposed change;
- compatibility, migration, consumer, producer, privacy, operational, and versioning impact;
- blocked child decisions and recommended parent revision path.
