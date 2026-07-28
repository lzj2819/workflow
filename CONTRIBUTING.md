# Contributing to VeriLayer

## Working rule

Use one branch and one pull request per bounded task. Do not commit directly to `main` after this initial publication.

1. Sync with `main`.
2. Create a branch named `member-a/<topic>`, `member-b/<topic>`, `member-c/<topic>`, or `member-d/<topic>`.
3. Work only inside the file ownership boundary defined in your member plan.
4. Run that plan's required checks and include their commands/results in the pull request.
5. Request review from the integration owner before merging.

## Shared contracts

Changes to artifact schemas, recursive node identifiers, root-orchestrator protocol, or evaluation metrics require an explicit contract-change note in the pull request. Do not silently update downstream consumers.

## Evidence and experiments

- Keep Tutor fixtures, historical artifacts, and hidden tests out of formal C0–C5 result directories.
- Store a completion package with the changed files, commands run, result, limitations, and rollback note.
- Report strict Mocktest execution completeness separately from architectural PASS/FAIL/WARNING.

## Never commit

- `.env` files, API keys, tokens, passwords, private keys, cookies, or real user data;
- `data/`, caches, logs, generated worktrees, or model downloads;
- a change that claims a simulated adapter or historical Tutor artifact is a fresh production run.
