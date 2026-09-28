---
id: BUG-03
title: - 2026-09-29 (STORY-142): `rvc issue <ID> start|done` fails its atomic `git mv` 
type: bug
priority: P2
origin: adlai-vault
submitted: 2026-09-29
---

# BUG-03: - 2026-09-29 (STORY-142): `rvc issue <ID> start|done` fails its atomic `git mv` 

- 2026-09-29 (STORY-142): `rvc issue <ID> start|done` fails its atomic `git mv` on filenames containing an apostrophe (`STORY-142-…self-disclaimed-'general-information'…`) — "fatal: bad source", falls back to a plain move. The transitions still landed, but state was briefly ambiguous (`AD` in the index until a manual add). Either quote the paths in the mv, or warn loudly when falling back.


## Fix (2026-09-29)

`git mv` / `git rm` paths are now `shlex.quote()`d (`rvc/issues.py`); no shell-string quoting to break. Regression: `tests/test_bugfixes_02_03_04.py::test_apostrophe_filename_transitions_cleanly` — creates `STORY-01-...plate-s-owed-lanes...` and transitions it to 30_ACTIVE asserting a real `git mv` (no fallback message).
