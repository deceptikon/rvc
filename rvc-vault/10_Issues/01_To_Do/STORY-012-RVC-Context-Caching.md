---
id: STORY-012
type: story
status: To Do
priority: P2
assignee: "@ai-dev"
epic: "[[EPIC-002]]"
created: 2026-06-28
tags: [conductor, issue, rvc, workflow]
title: RVC-Context-Caching
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
---

# STORY-012: RVC Context Caching & Token Optimization

## Context
Both `plan_node` and `act_node` call `_rvc_context()`, which shells out to `rvc context` or `rvc get`. For large vaults this can take 10–30 seconds and return 60–90K chars. Fetching twice per cycle doubles latency and token cost.

## Goal
Cache RVC context in `RunState` and provide smarter truncation options.

## Acceptance Criteria
- [ ] Add `rvc_context_data: str` to `RunState` (populated on first fetch).
- [ ] `plan_node` and `act_node` read from state instead of re-fetching.
- [ ] If `issue_id` or `rvc_mode` changes between plan and act (e.g., human edit), invalidate cache and re-fetch.
- [ ] Add `--rvc-summary` mode (future): truncate linked docs to first 500 chars + headers only.
- [ ] Verify token savings: `selftest` run with `--issue` should show prompt breakdown with `rvc` chars identical in plan and act.

## Test Case
```python
# Mock _rvc_context to return a fixed string and count calls.
state = {"issue_id": "STORY-01", "rvc_mode": "full"}
# After plan_node + act_node in the same cycle:
assert mock_rvc_context.call_count == 1
```
