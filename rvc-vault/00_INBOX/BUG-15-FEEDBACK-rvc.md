---
id: BUG-15
title: FEEDBACK-rvc
type: bug
priority: P2
origin: adlai-vault
submitted: 2026-11-06
---

# BUG-15: FEEDBACK-rvc

- 2026-11-06 (`rvc issue BUG-06 start`): the pre-transition `git pull --rebase` sync runs on a brand-new local branch with no upstream and prints a multi-line Git help block plus "Warning: Git pull failed". Harmless but noisy — it reads like the transition may have failed. An untracked branch should skip the sync silently.
- 2026-11-06 (`rvc plate`): crashed earlier in this session with `NameError: name '_plate_wrap' is not defined`; it renders fine on the re-run, so the upstream tree moved under it. No action — recorded only so the absence of a `FEEDBACK-rvc` entry for it is not read as an unreported bug.
- [2026-11-06] **`[skip ci]` by default makes a vault MR unmergeable.** Three `rvc` transitions on
  `docs/close-157-166` (MR !41) all carried `[skip ci]`, so the MR head got pipeline #540 in state
  `skipped`, and "Pipelines must succeed" blocked the merge — the owner could not click Merge. This is
  the second time today (`rvc issue BUG-06 done` needed `--no-skip-ci` for the same reason). Please make
  `rvc` detect that the current branch is an **open MR head** and default to `--no-skip-ci` there (or
  refuse and say why), and print a one-line hint: `vault commit on an MR branch → no pipeline → no merge`.
  `[skip ci]` is right for a doc-only commit pushed straight to `main`; on an MR branch it is a self-inflicted
  merge block. (`STORY-157`)

