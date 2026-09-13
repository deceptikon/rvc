---
id: STORY-009
type: story
status: To Do
priority: P0
assignee: "@ai-dev"
epic: "[[EPIC-002-Conductor-v0.2-Hardening]]"
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

## Prerequisites

- [[STORY-010]] (Unit Test Foundation) must be **Done** — provides mock workers, temp dirs, and pytest fixtures for testing PlanReviser in isolation.

## Acceptance Criteria
- [ ] Parse QA log for: test names, assertion failures, stack traces, syntax errors.
- [ ] Match failures to the node whose `test_case` or `artifact_path` is implicated.
- [ ] If a single node is clearly broken: revise only that node's `expected_output` and `test_case`, reset `qa_attempts` to 0, route back to `act`.
- [ ] If the failure is systematic (e.g., missing dependency, bad architecture): emit a revised full plan with changed `topo_order` or new nodes.
- [ ] If the plan is sound but execution keeps failing (flaky test / env issue): escalate to human with a summary.
- [ ] If the revised plan is identical to the previous one: route to `end` with `qa_failed` status (avoid infinite loops).
- [ ] **PlanReviser performs node-level diagnosis and revision** (e.g., `test_case_3_validation` failure) as shown in dream flow dry-run output.
- [ ] **G4 gate:** PlanReviser only activates after `qa_attempts >= max_qa_retries` AND `qa_passed == False`; never activates on first QA failure.
- [ ] **G2 gate:** PlanReviser validates revised plan JSON against `Plan` schema before routing back to `review`; if invalid, route to `end` with `qa_failed`.
- [ ] **Loop prevention:** hard limit on revision iterations (`max_revisions=3`); if reached, route to `end` with `qa_failed` and human escalation note.
- [ ] **G2.5 gate:** if QA log is empty or unreadable, PlanReviser logs warning and escalates to human instead of attempting blind revision.

## Test Case
Use `test_fixtures/fake-repo` with `qa-pass.sh` and `qa-fail.sh`:
1. Start a run with a plan containing a node whose `test_case` asserts `False`.
2. After 2 QA failures, PlanReviser should identify the broken node, revise its contract, and route back to `act`.
3. The next QA should pass.
4. **Additional test:** After `max_revisions=3` identical plans, PlanReviser routes to `end` with `qa_failed`.
5. **Additional test:** Empty QA log → human escalation, no infinite loop.

## Edge Cases & Error Scenarios

| Scenario | Expected Behaviour |
|----------|-------------------|
| QA log contains multiple unrelated failures | PlanReviser identifies the first failure's node; if ambiguous, escalates to human |
| Revised plan adds a new node but `topo_order` has cycle | G2 gate catches invalid plan → route to `end` with `qa_failed` |
| Worker returns non-JSON during diagnosis | Log error, route to `end` with `qa_failed`, do not retry |
| `max_qa_retries` is 0 (disabled) | PlanReviser never activates; QA failures route directly to `end` |
| Plan has no `test_case` fields | PlanReviser notes "no testable nodes" and escalates to human |

## Non-Functional Requirements

- **Performance:** Diagnosis must complete in <30s (single LLM call)
- **Determinism:** Same QA log + same plan → same diagnosis (no randomness in routing)
- **Observability:** Every PlanReviser activation logs: qa_attempts, diagnosis summary, revision type (node-level / full-plan / escalation), new plan version
- **Safety:** PlanReviser never deletes nodes from the plan; it can only modify, add, or split nodes
