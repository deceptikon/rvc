---
id: STORY-008
type: story
priority: P0
assignee: "@ai-dev"
epic: "[[EPIC-002-Conductor-v0.2-Hardening]]"
created: 2026-06-28
tags: [conductor, issue, workflow]
title: Eliminate-shell-True
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-008
---

# STORY-008: Security Hardening — Eliminate `shell=True`

## 2026-09-29 — this was filed as DONE and was not done

Found during a state pass. This file sat in `90_ARCHIVE/done/` with **all four acceptance criteria
unchecked**, including AC3 — "`rvc-cli.py` `run_cmd()` refactored to accept list commands" — which
is the one that matters. Verified at the time: `rvc/core.py:22` still
`subprocess.run(cmd, shell=True, ...)`, with **27 call sites** interpolating strings into it.

Worse, the unsafe primitive had already caused a real defect: **BUG-03** (2026-09-29), where a
vault issue whose title contained an apostrophe made `git mv` fail with `fatal: bad source` and the
transition silently degraded to a plain move. The fix was `shlex.quote` at the call site — a
band-aid on a hole that is still open, applied to 2 of 27 sites.

**This is the mirror image of STORY-030's complaint, and the more dangerous direction.** There, a
live bug was filed as fixed and nobody could tell. Here, a nonexistent fix was filed as live, and
the archive — the one folder a reader trusts as settled history — asserted it.

**Superseded by [[STORY-013]]**, rescoped 2026-09-29 to this single criterion. Moved out of `done/`
so the archive stops making the claim.

## Context
The QA node in `conductor/pipeline.py` uses `subprocess.run(..., shell=True)` to execute the project's QA command. While `qa_cmd` is currently sourced from a trusted TOML file, this is a latent command-injection vulnerability if any future UI or config path allows user-controlled input. Additionally, `rvc-cli.py` uses `shell=True` for all git operations.

## Acceptance Criteria
- [ ] `qa_node` in `pipeline.py` uses `shlex.split(cfg.qa_cmd)` + `shell=False`.
- [ ] Backwards-compat shim: try `shlex.split` first, fall back to `shell=True` with a warning if splitting fails.
- [ ] `rvc-cli.py` `run_cmd()` refactored to accept list commands; all git calls use list form.
- [ ] `conductor selftest adlai` still passes after the change.

## Test Case
```python
# In tests/test_pipeline.py
def test_qa_node_uses_shell_false():
    # Mock cfg.qa_cmd = "pytest -q"
    # Assert subprocess.run called with ["pytest", "-q"], shell=False
```
