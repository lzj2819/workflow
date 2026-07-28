# VeriLayer

VeriLayer is an evidence-oriented, layered AI software-development workflow:

`Requirement → PRD → Architecture + Gherkin → Mocktest → Leaf-gate → recursive decomposition → coding and tests`.

This repository contains the current research workspace, the four-person ten-day implementation plan, reusable workflow components, and the read-only Tutor migration fixture.

## Start here

- [Project workflow](工作流总文档.md)
- [Ten-day implementation plan](VERILAYER_10_DAY_IMPLEMENTATION_PLAN.md)
- [Four-person start guide](VERILAYER_FOUR_PERSON_START_GUIDE.md)
- [Member A plan](team-plans/VERILAYER_MEMBER_A_IMPLEMENTATION_PLAN.md)
- [Member B plan](team-plans/VERILAYER_MEMBER_B_IMPLEMENTATION_PLAN.md)
- [Member C plan](team-plans/VERILAYER_MEMBER_C_IMPLEMENTATION_PLAN.md)
- [Member D plan](team-plans/VERILAYER_MEMBER_D_IMPLEMENTATION_PLAN.md)

## Current scope

The root orchestration and simulated adapters are available. Production-grade cross-module artifact contracts, Architecture/Gherkin executors, and the complete Coding Executor are planned P0 work; do not treat the Tutor fixture or simulated execution as proof of a production end-to-end coding system.

The `tutor/` tree is a migration fixture and evidence source. It is not part of the formal C0–C5 benchmark and must remain isolated from hidden tests and fresh experiment results.

## Collaboration

Create a short-lived branch from `main`, keep a change within the owner boundary in the member plan, run the stated verification, then open a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Publication hygiene

This public release is built from a sanitized working copy. Environment files, data directories, local caches, logs, generated worktrees, and local machine paths in executable configuration are excluded. Never commit credentials or real user/business data.

Third-party reference PDFs remain local until their redistribution status is reviewed; the accompanying reference notes are retained.
