---
id: EPIC-002
type: epic
status: To Do
priority: P1
assignee: "@ai-dev"
epic: 
created: 2026-06-28
tags: [conductor, issue, workflow]
title: Conductor-v0.2-Hardening
domain: workflow_meta
domain_tags: ["rvc", "protocol", "epic"]
---

# EPIC-002: Conductor v0.2 — Production Hardening & Intelligence

## Problem Statement
The Conductor harness is architecturally sound but has three critical gaps: (1) security (`shell=True` in QA node), (2) missing autonomy (PlanReviser is a stub), and (3) no test coverage. Without these, it remains a demo rather than a production-grade agent orchestrator.

## Goal
Harden the Conductor pipeline for daily autonomous use, add real failure-diagnosis intelligence, and establish a test foundation so future features don't regress.

## Requirements
- [ ] Security hardening: eliminate `shell=True` from QA and worker paths.
- [ ] Real PlanReviser node that diagnoses QA failures and revises plans.
- [ ] Unit test foundation for schema validation, worker parsing, and routing logic.
- [ ] Parallel DAG execution for independent plan nodes.
- [ ] RVC context caching to avoid duplicate fetches.
- [ ] Structured contracts (JSONSchema) for `expected_output` / `test_case`.

## Acceptance Criteria
1. `pytest` passes with >80% coverage on `schema.py` and `workers.py`.
2. A QA failure cycle (plan → act → qa fail → plan_reviser → act → qa pass) completes without human intervention in `test_fixtures/`.
3. `conductor selftest` reports zero lint/type errors.
4. `rvc context` is fetched at most once per run cycle.

## Linked Stories
- [[STORY-008]] — Security Hardening: `shell=True` Removal
- [[STORY-009]] — Real PlanReviser with QA Log Diagnosis
- [[STORY-010]] — Unit Test Foundation
- [[STORY-011]] — Parallel DAG Execution in Act Node
- [[STORY-012]] — RVC Context Caching & Token Optimization
