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
rescoped: 2026-09-29
---

# STORY-013: kill `shell=True` (rescoped 2026-09-29)

## Rescope: the performance half was a false premise; the security half is a live bug class

On 2026-09-29 this issue was cut from five criteria to one. The reasoning is measured, not stylistic:

- **AC1 is not a hypothetical.** `rvc/core.py:22` still runs `subprocess.run(cmd, shell=True)`, and
  **27 call sites** interpolate strings into it — `f"git commit -m '{message}'"`,
  `f"git mv {shlex.quote(a)} {shlex.quote(b)}"`, `run_cmd(f"git rm -q -- '{src}'")`. Six hours
  before this rescope that primitive produced **BUG-03**: a vault issue whose title contained an
  apostrophe made `git mv` fail with `fatal: bad source`, and the transition silently degraded to a
  plain move. The fix was `shlex.quote` *at the call site* — a band-aid on an unsafe primitive, and
  only 2 of 27 sites were treated. The class is open.
- **The same work was already faked as done.** `90_ARCHIVE/done/STORY-008-Eliminate-shell-True.md`
  sits in the *done* archive with all four acceptance criteria unchecked, including this exact one
  ("`rvc-cli.py` `run_cmd()` refactored to accept list commands"). The vault currently carries a
  ticket asserting a security fix that was never made. That is the mirror image of STORY-030's
  complaint, and it is worse: there, a live bug was filed as fixed; here, a dead fix was filed as live.
- **AC2/AC3 are dropped — the index was solving a problem this vault does not have.** The `O(n²)`
  claim assumed a vault large enough for `os.walk` to bite. `rvc-vault` holds **~30 markdown files**;
  `adlai-vault` a few hundred. `build_vault_index()` walks the whole tree per call and the plate
  renders in well under a second. A persisted `.rvc-index.json` would be a second source of truth
  for folder-as-state, needing invalidation on every transition — real complexity, zero measured
  benefit, and a new way for the record to lie. **The index is the wrong shape of answer.**
- AC4/AC5 stay closed: `vault_create_lock()` (`flock` on `.rvc-create.lock`) and
  `tests/test_create_concurrency.py` (8 real processes) are landed and passing.

## Acceptance criteria (rescoped — one criterion)

1. **`run_cmd()` takes a list and runs `shell=False`; zero `shell=True` remains in the git path.**
   - `run_cmd(cmd, cwd=None, shell=False)` where `cmd` is a `list[str]`. The `shell=True` branch is
     deleted, not defaulted — a string argument must fail loudly, not silently re-open the hole.
   - All 27 call sites converted, including the three that interpolate a **user-supplied commit
     message** (`rvc/git.py:222,266`) — the actual injection surface, since a title like
     `fix: don't "break" the parser` must land as a message, not as shell syntax.
   - `rvc-sync.py:9` is the same bug in a second file; fix it or delete it, do not leave it.
   - Regression test: an issue title containing `'; rm -rf ~; echo '` round-trips through
     `create → start → done` and the commit message is the literal title, with no side effect.
   - BUG-03's existing test (`test_bugfixes_02_03_04.py::test_apostrophe_filename_transitions_cleanly`)
     must stay green — list-form is the *real* fix for the bug it was band-aided.

## Test case

```bash
rvc create "it's a trap; touch /tmp/pwned -- 'quoted'" && rvc issue <ID> start && rvc issue <ID> done
test ! -e /tmp/pwned && git log -1 --format=%s   # message is the literal title
```

## Definition of done

- `grep -rn "shell=True" rvc/ rvc-cli.py rvc-sync.py` returns nothing
- `STORY-008` is moved out of `90_ARCHIVE/done` and superseded by this file, so the archive stops
  claiming a fix that does not exist
- The full stdlib suite (`python3 tests/run_tests.py`) is green
