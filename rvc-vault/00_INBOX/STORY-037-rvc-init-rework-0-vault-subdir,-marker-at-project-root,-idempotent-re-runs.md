---
id: STORY-037
title: rvc init rework: 0-vault subdir, marker at project root, idempotent re-runs
type: story
priority: P1
started: 2026-09-19
---

# STORY-037: rvc init rework: 0-vault subdir, marker at project root, idempotent re-runs

`rvc init` has two modes (`init` flat vs `project init` subdir) and a legacy/newvault
`--tree` choice — but the natural command produces the wrong shape for real projects
(RVC has `rvc-vault/`, ADLAI has `adlai-vault/`; nobody drops the bucket tree into the
project root). Decision (2026-09-19, request from user):
one stable command, always the same result, no legacy/new logic.

# Behavior (the contract)

1. `rvc init` in a new project creates a `0-vault/` directory with the new (newvault)
   structure in it: `00_INBOX 10_CONTEXT 20_NEXT 30_ACTIVE 40_DECIDE 50_DEFERRED 60_DONE
   90_ARCHIVE .obsidian`, plus `10_CONTEXT/ROUTING.md`.
2. `.rvc-root` and `.gitignore` are handled **outside** the vault dir, at the project
   root:
   - `.rvc-root`: `vault=0-vault` + the `tree.*` block (paths relative to the vault).
   - `.gitignore`: the RVC/Obsidian volatile-state lines (deep-matched).
   - Project root also gets the AGENTS/CLAUDE/GEMINI/QWEN links → `0-vault/10_CONTEXT/ROUTING.md`
     and a README.
3. Re-running `rvc init` never overwrites: it appends missing files and missing
   `.gitignore`/`.rvc-root` lines only. Existing user content stays untouched.
4. No `--tree legacy|newvault` flag anymore — init always produces the new structure.
   `rvc project init` folds into the same behavior.

# Mechanics (resolution)

- Marker lives at the project root; the vault dir has no marker of its own.
- `find_vault_root` descends via `vault=<rel>` when that child dir exists and has no
  marker of its own (self-referential inner markers like `vault=scratch` in old vaults
  keep resolving to their own dir — no recursion, no breakage).
- Config readers that assume `<vault>/.rvc-root` (`read_tree_config`, `_push_enabled`,
  `read_plate_config`, feedback `_feedback_target`/`_ensure_feedback_config`) resolve the
  marker at the project root instead, so plate lanes, push opt-in and the automatic
  feedback config all keep working under the new layout.

# Acceptance criteria

- AC1 — `rvc init <project>` creates `0-vault/` with the full new tree; marker + gitignore
  at project root; AGENTS links + README at project root; nothing inside `0-vault/` except
  the buckets/ROUTING.
- AC2 — second run is additive: identical tree, no duplicate gitignore/marker lines,
  existing ROUTING kept verbatim.
- AC3 — from the project root and from inside `0-vault/`, `rvc plate`/`rvc issue list`
  resolve the same vault (find_vault_root descent via `vault=`).
- AC4 — old layouts still resolve: flat marker (no `vault=`) and inner self-ref markers
  (`vault=scratch`) return the same vault as before (no regression).
- AC5 — `--tree` flag gone from CLI/help; `rvc project init` still works (same result).
- AC6 — `rvc feedback` auto-config lands in the *project-root* marker (nothing written
  inside `0-vault/`), and the full ingest → plate lane loop works under the new layout.

# DoD

- Suite green (all prior 96 + new init tests).
- Sandbox revalidated under the new layout: init → feedback → plate lane → lifecycle.
