---
type: note
tags: [feedback, rvc]
created: 2026-09-17
author: opencode
---

# FEEDBACK — rvc

- **2026-09-17 (STORY-129, opencode):** `rvc issue start` on an issue file that was never committed (`??` under `20_NEXT/`) prints a three-warning cascade — pull-abort on unrelated unstaged WIP (`cannot pull with rebase: You have unstaged changes`), then `git mv failed (fatal: not under version control, …)`, then `could not stage <old path>` — before recovering to a plain move + add. The transition lands correctly, but the output reads like failure and cost a verification round-trip. Either `rvc create` should always commit the new file, or `start` should say "untracked source — falling back to plain move" instead of citing raw `git mv` fatals.
- **2026-09-17 (STORY-130, opencode):** `rvc create --body` duplicates the H1 — the CLI inserts `# STORY-<n>: <title>` and appends the body verbatim, so a body that opens with its own title heading renders it twice (edited out by hand). Also: a successful `create` leaves `.rvc-create.lock` (`pid=<dead>`) behind in the vault root; it accumulates untracked until someone deletes it, and a stale `pid=` file is indistinguishable from an active lock without a liveness check.
- **2026-09-18 (STORY-137, opencode):** both 2026-09-17 items reproduced. The pull-abort on unrelated unstaged WIP (`cannot pull with rebase: You have unstaged changes`) fired on `start` *and* `done`; `.rvc-create.lock` still accumulates after `create`. Transitions continue to land correctly, so this is output/cleanup noise, not data loss — but it re-costs a verification round-trip each time.
- **2026-09-19 (superseded, opencode):** all three items executed and verified in RVC — **STORY-035** (quiet untracked transitions, `--body` H1 dedup, lock cleanup + liveness). This copy was moved (not deleted) here from `adlai-vault/00_INBOX/` as an exceptional handoff: the letter belongs to RVC's vault, where the record now lives.