---
id: STORY-013
type: story
status: To Do
priority: P1
assignee: "@ai-dev"
epic: "[[EPIC-001]]"
created: 2026-06-28
tags: [issue, rvc, workflow]
title: RVC-Security-Performance
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
---

# STORY-013: RVC CLI Security & Performance Hardening

## Context
`rvc-cli.py` uses `shell=True` for all subprocess calls and `os.walk()` for all file lookups. This creates security vulnerabilities and `O(n²)` performance as the vault grows.

## Acceptance Criteria
- [ ] Refactor `run_cmd()` to accept list commands; remove `shell=True` from all git operations.
- [ ] Add a simple JSON index (`.rvc-index.json`) in the vault root mapping `ID → filepath`. Update on every write operation (`create`, `issue start/review/done`).
- [ ] `find_file_by_id()` reads from index first, falls back to `os.walk` with a warning if index is stale.
- [ ] `_next_id()` uses filesystem locking (`fcntl` on Linux, `msvcrt` on Windows) or atomic writes to prevent duplicate IDs.
- [ ] Add tests for index consistency and ID generation under concurrency.

## Test Case
```bash
# Create 100 issues in a loop
for i in {1..100}; do rvc create "Test $i"; done
# rvc issue list should complete in < 1 second (uses index, not walk)
```
