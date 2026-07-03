---
id: STORY-011
type: story
status: To Do
priority: P1
assignee: "@ai-dev"
epic: "[[EPIC-002]]"
created: 2026-06-28
tags: [conductor, issue, workflow]
title: Parallel-DAG-Execution
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-011
---

# STORY-011: Parallel DAG Execution in Act Node

## Context
The current `act_node` sends the *entire* locked plan to a single worker, which presumably implements all nodes sequentially. For plans with independent branches (e.g., "add tests" and "update docs" as parallel tasks), this wastes wall-clock time.

## Goal
Execute independent plan nodes in parallel while respecting dependencies.

## Acceptance Criteria
- [ ] `Plan.compute_topo_order()` already produces a valid topological sort. Use it to group nodes by dependency depth.
- [ ] Nodes at the same depth with no inter-dependencies execute in parallel via `concurrent.futures.ThreadPoolExecutor`.
- [ ] Each parallel worker receives: contract + its node definition + upstream outputs (if any).
- [ ] If any parallel worker fails, collect all outputs/logs and route to QA as usual.
- [ ] Max parallel workers capped by config (default: 3) to avoid overwhelming the local LLM server.
- [ ] Backwards compatible: single-node plans behave exactly as before.

## Test Case
Create a plan with two independent nodes:
1. `node_a`: create file A
2. `node_b`: create file B
3. `node_c`: merge A and B (depends on a and b)

Measure that `node_a` and `node_b` start within 5 seconds of each other.
