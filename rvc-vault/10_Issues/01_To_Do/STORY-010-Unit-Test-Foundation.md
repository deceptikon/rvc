---
id: STORY-010
type: story
status: To Do
priority: P1
assignee: "@ai-dev"
epic: "[[EPIC-002]]"
created: 2026-06-28
tags: [conductor, issue, workflow]
title: Unit-Test-Foundation
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
---

# STORY-010: Unit Test Foundation

## Context
Conductor has zero automated tests. The `test_fixtures/` directory is for manual QA gate testing only. As the pipeline grows more complex (PlanReviser, parallel execution, structured contracts), regressions will become inevitable without tests.

## Goal
Establish a pytest-based test suite covering the core logic layers.

## Acceptance Criteria
- [ ] `tests/test_schema.py` — Tests for `Plan.validate()`:
  - DAG with no cycles passes.
  - Cycle detection works (A→B→C→A).
  - Missing dependency flagged.
  - Empty `expected_output` / `test_case` flagged.
  - `topo_order` mismatch flagged.
- [ ] `tests/test_workers.py` — Tests for `_extract_stream_json()`:
  - Valid stream-json lines parsed correctly.
  - Malformed lines handled gracefully (not dropped silently without log).
  - Mixed valid/invalid input returns best-effort result.
- [ ] `tests/test_pipeline_routing.py` — Tests for conditional edges:
  - `after_approve`: rejected → plan, reviewing → review, approved → act.
  - `after_qa`: passed → commit, attempts < max → act, attempts >= max → plan_reviser.
  - `after_reviewer`: locked → approve, invalid → plan.
- [ ] CI-ready: `uv run pytest` passes in the repo root.

## Test Case
```bash
uv run pytest tests/ -q
# Expected: 15+ tests, all passing
```
