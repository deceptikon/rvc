---
id: STORY-008
type: story
status: To Do
priority: P0
assignee: "@ai-dev"
epic: "[[EPIC-002]]"
created: 2026-06-28
tags: [conductor, issue, workflow]
title: Eliminate-shell-True
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
---

# STORY-008: Security Hardening — Eliminate `shell=True`

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
