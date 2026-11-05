---
id: BUG-09
title: concurrent creates mint duplicate ids — create-lock unlink/replacement race
type: bug
priority: P1
started: 2026-11-06
---

# BUG-09: concurrent creates mint duplicate ids — create-lock unlink/replacement race

Found regression-testing BUG-05: `tests/test_create_concurrency.py` (8 forked creates) intermittently mints duplicate ids — non-sequential [1,2,3,4,5,6,6,7] — roughly 1 run in 3, reproducible on the pre-fix tree too. Root cause: `vault_create_lock` unlinks the lock file on exit (STORY-130 no-residue cleanup). A waiter that already opened the old inode keeps queuing on it after the unlink; a later opener creates a replacement file and locks it uncontended — old-inode waiter and fresh holder then run the mint critical section concurrently. The contextmanager comment even documents the hole ("a brand-new opener after the unlink starts fresh") as if it were safety. Fix: after acquiring the flock, re-stat — only proceed when the path still names our inode; a waiter on a replaced inode releases and retries on the current file.
