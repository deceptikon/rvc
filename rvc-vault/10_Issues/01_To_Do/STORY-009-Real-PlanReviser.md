---
id: STORY-009
type: story
status: To Do
priority: P0
assignee: "@ai-dev"
epic: "[[EPIC-002]]"
created: 2026-06-28
tags: [conductor, issue, workflow]
title: Real-PlanReviser
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-009
---

# STORY-009: Real PlanReviser with QA Log Diagnosis

## Context
The current `plan_reviser_node` in `conductor/pipeline.py` is a stub. When QA fails `max_qa_retries` times, it generically asks the planner to "diagnose" without structured analysis. The system cannot autonomously recover from test failures — it just gives up or loops blindly.

## Goal
Build a real diagnosis engine that parses QA output, matches failures to plan nodes, and produces targeted plan revisions.

## Acceptance Criteria
- [ ] Parse QA log for: test names, assertion failures, stack traces, syntax errors.
- [ ] Match failures to the node whose `test_case` or `artifact_path` is implicated.
- [ ] If a single node is clearly broken: revise only that node's `expected_output` and `test_case`, reset `qa_attempts` to 0, route back to `act`.
- [ ] If the failure is systematic (e.g., missing dependency, bad architecture): emit a revised full plan with changed `topo_order` or new nodes.
- [ ] If the plan is sound but execution keeps failing (flaky test / env issue): escalate to human with a summary.
- [ ] If the revised plan is identical to the previous one: route to `end` with `qa_failed` status (avoid infinite loops).

## Test Case
Use `test_fixtures/fake-repo` with `qa-pass.sh` and `qa-fail.sh`:
1. Start a run with a plan containing a node whose `test_case` asserts `False`.
2. After 2 QA failures, PlanReviser should identify the broken node, revise its contract, and route back to `act`.
3. The next QA should pass.
