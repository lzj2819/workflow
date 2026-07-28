# Tutor Current-State Reconciliation

Status: Day 1 control-plane reconciliation baseline. Historical documents are evidence snapshots, not automatically current state.

## Reconciled state

| Evidence source | Evidence time | Current interpretation | Superseded by | Claim scope |
|---|---|---|---|---|
| `run-manifest.md` in `tutor-r01` | historical run snapshot | manual coordination; records 16/17 and earlier blockers | later task registry, CCR-001, GAP-02, and vendor reports | historical execution snapshot only |
| `task-registry.md` in `tutor-r01` | later than run manifest, internally mixed | leaf table reports 17/17 done; header/footer retain stale pending text | later explicit closure records where present | task-registry evidence, not production workflow evidence |
| `contract-freeze.md`, `findings.md`, `progress.md` | later control-plane records | CCR-001 reported completed | none identified in the Day 1 inventory | historical project-state evidence |
| `d4-staging-acceptance-report.md`, `gap-02-verification-report.md`, `vendor-integration-report.md` | staged follow-up reports | NFR relay/ICT and provider stub checks reported closed | none identified in the Day 1 inventory | bounded staging/stub evidence |
| release readiness and E2E reports | 2026-07-21 to 2026-07-22 historical snapshots | contain then-open items | later reports may close individual items | historical report, not current release approval |

## Still not established

- A production `run-workflow` execution.
- A common Coding Executor and fair C0-C5 experiment configuration.
- A real-key DeepSeek staging call, formal release human Gate, or course-term SM metrics.
- Independent Leaf ground truth: the existing STOP labels include product-owner terminal decisions.

## Reconciliation rule

Every imported historical artifact must carry `evidence_time`, `superseded_by`, and `claim_scope` in its migration metadata. If these values cannot be established, the Adapter must classify the result as `ERROR`/unresolved provenance and block use as current experimental evidence.
