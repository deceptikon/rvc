---
id: STORY-035
title: rvc feedback: quiet untracked transitions, body H1 dedup, lock cleanup
type: story
priority: P1
epic: [[EPIC-001-RVC-Protocol]]
started: 2026-09-19
---

# STORY-035: rvc feedback: quiet untracked transitions, body H1 dedup, lock cleanup

**Origin:** `00_INBOX/FEEDBACK-rvc.md` (2026-09-17/18) — three output-noise / cleanup
defects observed by opencode agents on live transitions, reproduced on both dates.

## Defect 1 — Transitions on never-committed issues cascade raw git errors

`rvc issue start` / `done` on an issue file that was never committed (`??` under a
bucket) printed three warnings — the pull-abort on unrelated unstaged WIP
(`cannot pull with rebase: You have unstaged changes`), `git mv failed (fatal:
not under version control, …)`, then `could not stage <old path>` — before
recovering to a plain move + add. The transition landed correctly, but the output
read like failure and cost a verification round-trip.

**Fix:** `sync_before` skips `git pull --rebase` when the tree is dirty (no raw
git abort); `cmd_issue_action` detects an untracked source and takes a plain move
with a friendly note; `sync_after` only `rm --cached`s paths that exist in the
commit index.

## Defect 2 — `create --body` duplicates the H1

The CLI inserts `# <ID>: <title>` and appends the body verbatim, so a body that
opens with its own title heading renders twice.

**Fix:** strip one redundant leading H1 from the body; the canonical heading
always wins.

## Defect 3 — `.rvc-create.lock` accumulates with a dead `pid=`

A successful `create` left `.rvc-create.lock` (`pid=<dead>`) behind at the vault
root; a stale marker was indistinguishable from an active lock without a liveness
check.

**Fix:** the lock file is removed on exit (only while the path still names the
inode we locked, so a replacement file is never deleted); a stale `pid=` naming a
dead process is reclaimed with an explicit notice; timeout messages report the
holder pid.

---

## Acceptance Criteria

- [ ] **AC 1: Untracked transitions are calm** — `start`/`done` on a `??` file
      move it, commit it, and print no raw git fatal (`cannot pull with rebase`,
      `git mv failed`, `could not stage` all absent).
- [ ] **AC 2: Tracked transitions still rename** — a tracked source still commits
      as a `git mv` rename, with no "untracked" note.
- [ ] **AC 3: `--body` H1 deduplicated** — a body opening with `# Title` renders
      exactly one H1 (the canonical `# <ID>: <title>`).
- [ ] **AC 4: Lock cleaned up, stale reclaimed** — after a successful create the
      lock file is gone; a lock naming a dead pid is reclaimed, not treated as held.
- [ ] **AC 5: Suite green** — stdlib runner passes (85 passed, 0 failed) with
      regression tests in `test_create_body_h1.py`, `test_issue_action_untracked.py`,
      `test_create_concurrency.py`.

## Definition of Done

- All five ACs pass.
- `10_CONTEXT/DECISIONS.md` + `10_CONTEXT/GOTCHAS.md` updated.
- This story transitions to `60_DONE` through the fixed CLI itself.
