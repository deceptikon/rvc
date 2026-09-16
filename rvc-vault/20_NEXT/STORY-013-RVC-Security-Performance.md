---
id: STORY-013
type: story
priority: P1
assignee: "@ai-dev"
epic: "[[EPIC-002-Conductor-v0.2-Hardening]]"
created: 2026-06-28
tags: [issue, rvc, workflow]
title: RVC-Security-Performance
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-013
---

# STORY-013: RVC CLI Security & Performance Hardening

## Context
`rvc-cli.py` uses `shell=True` for all subprocess calls and `os.walk()` for all file lookups. This creates security vulnerabilities and `O(n²)` performance as the vault grows.

## Acceptance Criteria
- [ ] Refactor `run_cmd()` to accept list commands; remove `shell=True` from all git operations.
- [ ] Add a simple JSON index (`.rvc-index.json`) in the vault root mapping `ID → filepath`. Update on every write operation (`create`, `issue start/review/done`).
- [ ] `find_file_by_id()` reads from index first, falls back to `os.walk` with a warning if index is stale.
- [x] `_next_id()` uses filesystem locking (`fcntl` on Linux, `msvcrt` on Windows) or atomic writes to prevent duplicate IDs.
      Landed for POSIX: `vault_create_lock()` holds an exclusive `flock` on `.rvc-create.lock`
      (vault root, git-ignored) across the mint+write critical section. Windows/`msvcrt` path not
      implemented — deployment is Linux-only today.
- [x] Add tests for ID generation under concurrency — `tests/test_create_concurrency.py` spawns 8
      processes and asserts unique, sequential IDs. Index-consistency tests remain coupled to
      `.rvc-index.json` (AC2).

## Test Case
```bash
# Create 100 issues in a loop
for i in {1..100}; do rvc create "Test $i"; done
# rvc issue list should complete in < 1 second (uses index, not walk)
```
