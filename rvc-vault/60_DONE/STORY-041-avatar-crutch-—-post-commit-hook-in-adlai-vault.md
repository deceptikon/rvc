---
id: STORY-041
title: avatar crutch — post-commit hook in adlai-vault
type: story
priority: P1
epic: [[EPIC-004]]
started: 2026-09-29
---

# STORY-041: avatar crutch — post-commit hook in adlai-vault

Thin wiring, v0 already fired live once. A post-commit hook in adlai-vault calls `avatar notify` after every commit — the vault itself asks the bot to ping NEW owed turns. No daemon, no cron habit; dedupe state keeps it silent when nothing changed. Event-driven fits folder-as-state: a transition IS a commit.

## Acceptance criteria

1. ✅ `avatar hook <vault-path>` installs an idempotent `.git/hooks/post-commit` that
   fire-and-forgets `avatar notify --vault <path>` into a log — commits never block.
   Hooks resolve via `git rev-parse --absolute-git-dir` (adlai-vault turned out to be a
   submodule — hooks live in `~/X/.git/modules/ADLAI/hooks/`, not in the vault dir).
2. ✅ Installed in `/home/lexx/X/ADLAI/adlai-vault`; executing the hook by hand against the
   real plate ends-to-end: vault → `rvc plate` → avatar — the log carries the honest
   `@salwa owes 1 but has no chat_id` line. The wiring is real, no fake ping was staged.
3. ✅ Re-running the installer does not duplicate the hook block (marker check — verified).
