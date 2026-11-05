---
id: BUG-09
title: concurrent creates mint duplicate ids — create-lock unlink/replacement race
type: bug
priority: P1
started: 2026-11-06
---

# BUG-09: concurrent creates mint duplicate ids — create-lock unlink/replacement race

Found regression-testing BUG-05: `tests/test_create_concurrency.py` (8 forked creates) intermittently mints duplicate ids — non-sequential [1,2,3,4,5,6,6,7] — roughly 1 run in 3, reproducible on the pre-fix tree too. Root cause: `vault_create_lock` unlinks the lock file on exit (STORY-130 no-residue cleanup). A waiter that already opened the old inode keeps queuing on it after the unlink; a later opener creates a replacement file and locks it uncontended — old-inode waiter and fresh holder then run the mint critical section concurrently. The contextmanager comment even documents the hole ("a brand-new opener after the unlink starts fresh") as if it were safety. Fix: after acquiring the flock, re-stat — only proceed when the path still names our inode; a waiter on a replaced inode releases and retries on the current file.

## Resolution (2026-11-06)

Two independent races, both pre-existing (reproduced on the pre-session tree, ~1 run in 3):

1. **Lock-file replacement race.** `vault_create_lock` unlinks the lock file on exit
   (STORY-130 cleanup). A waiter still holding the retired inode open acquired its flock
   while a later opener created and locked a replacement — two holders in the mint
   critical section, duplicate ids (`[1,2,3,4,5,6,6,7]`). Fix: after acquiring the flock,
   the path must still name our inode (`_lock_path_is_current`); a waiter on a retired
   inode releases and retries on the current file.
2. **Torn `.rvc-root` read.** `bump_mint_floor` rewrites the marker truncate-then-write
   on every mint, while `resolve_tree` runs *outside* the create lock — a reader hitting
   the truncation window saw an empty marker, resolved the LEGACY tree, and filed a
   minted issue into `10_Issues/01_To_Do` (the "missing minted file" flake). Fix: all
   marker rewrites are atomic (temp file + `os.replace`, `core._atomic_write_text`);
   readers see old or new content, never empty.

Verification: 40/40 strict stress runs clean (unique sequential ids, every file in the
create bucket, zero strays), 12/12 module runs, full suite 123 passed / 0 failed.
`test_concurrent_creates_mint_unique_ids` now scans for strays outside `00_INBOX` —
per-path existence checks could not see this class.
