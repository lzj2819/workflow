# 06 Leaf Decision — MOD-03

## Decision

`MOD-03` stops layering at L1. It has no direct `child_id` and must not produce an L2 PRD.

## Rationale

`REQ-D001` and `REQ-D002` form one bounded course-membership-verification responsibility. `CMP-MEMBERSHIP-VERIFIER` and `CMP-COURSE-ROSTER-ADMIN` remain internal implementation components of MOD-03: they introduce neither an independent product delivery boundary nor an independent deployment boundary.

## Implementation boundary

Implement the two internal components directly from the inherited contracts, state ownership, and LCD-001 through LCD-005. This decision does not alter CT-003, CT-013, FLOW-011, or the parent requirement semantics.

## Evidence

- Product-owner decision: MOD-03 is a leaf node.
- `leaf-gate.config.json`: `max_scenario_points` is 15 for this bounded node.
- `architecture-manifest.yaml`: `children` is empty and both components are marked `l2_target: false`.
