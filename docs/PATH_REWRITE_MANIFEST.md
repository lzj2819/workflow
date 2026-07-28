# Path Rewrite Manifest

Status: Day 1 policy. No paths are rewritten or executed by this document.

## Canonical path policy

- Formal artifacts, schema references, configuration, and handoff packages use repository-relative POSIX-style paths.
- Historical absolute paths are provenance only. They are not executable configuration and are never emitted by a canonical Adapter.
- A relocation must resolve beneath the intended repository root. Any escape, missing target, or ambiguous source fails closed with `status: ERROR`.

## Mapping rules

| Legacy reference | Canonical form | Result when unresolved |
|---|---|---|
| Tutor design artifact | `tutor/tutor/...` repository-relative provenance path | `ERROR` with `PATH_UNRESOLVED` |
| Tutor application/run evidence | `tutor/tutor-app/...` repository-relative provenance path | `ERROR` with `PATH_UNRESOLVED` |
| VeriLayer workflow artifact | `vibe coding/...` repository-relative path | `ERROR` with `PATH_UNRESOLVED` |
| Member-local root / drive / home path | omitted from shared artifact; kept only in local environment manifest | `ERROR` with `LOCAL_PATH_FORBIDDEN` |
| `.env`, cache, Git/worktree, data path | never relocatable or includable | `ERROR` with `EXCLUDED_SOURCE_PATH` |

## Adapter requirements

1. Resolve only a repository-relative input path against the selected repository root.
2. Verify the resolved path remains below that root before reading or hashing it.
3. Write `content_path` as the normalized repository-relative path and `content_sha256` from file bytes.
4. Preserve any legacy path only in redacted provenance metadata; never in a command, `content_path`, or error message.
5. Do not create a compatibility rewrite for the misspelled Architecture directory; the only canonical logical name is `prd-to-architecture-skill`.
