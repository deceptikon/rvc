---
id: EPIC-003
type: epic
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags:
  - planning
  - story
  - contract
  - pipeline
  - storywriter
alias: EPIC-003
---

# EPIC-003: Pre-Planning Storywriter & Contract Creation Pipeline

## Summary

Introduce two new subflows **before** the existing `plan` node in [`pipeline.py`](../../conductor/pipeline.py): a **Storywriter subflow** that researches and refines a high-level requirement into a finalized story, and a **Contract Creation subflow** that transforms the story into a dynamic technical contract—extending and eventually replacing the static AGENTS.md read at [`pipeline.py:83`](../../conductor/pipeline.py:83).

## Context & Motivation

The existing pipeline begins at `plan_node`, which receives a raw `task` string and operates against a static contract read from `AGENTS.md`. There is no automated step to:

- Validate that the requirement is well-understood before planning
- Create a traceable RVC vault story entry for the run
- Derive a task-specific technical contract from the story's Definition of Done

This epic adds that lifecycle, keeping the post-planning pipeline (`review → approve → act → qa → commit`) **entirely unchanged**.

## Proposed Full Pipeline Flow (post-epic)

```
START
  └─► story_research
        └─► story_draft
              └─► story_review ──[valid]──────────► rvc_link
                    └─[invalid, retries < 2]─► story_draft (loop)
                    └─[invalid, retries ≥ 2]─► HitL interrupt()
                                                        └─► story_draft (resume)
                                    rvc_link
                                        └─► contract_propose
                                              └─► contract_validate ──[valid]──► plan
                                                    └─[invalid]─► contract_propose (loop)
plan ──► review ──► approve ──► act ──► qa ──► commit ──► END
```

## Child Stories

| ID | Title | Type |
|----|-------|------|
| [[STORY-015-RunState-Story-Contract-Lifecycle]] | Extend `RunState` with story & contract lifecycle fields | Technical |
| [[STORY-016-Story-Research]] | `story_research` node: codebase & RVC impact analysis | Functional |
| [[STORY-017-Story-Draft]] | `story_draft` node: narrative story generation | Functional |
| [[STORY-018-Story-Review-Retry]] | `story_review` node: validation, retry loop & HitL escalation | Functional |
| [[STORY-019-RVC-Link]] | `rvc_link` node: create & link RVC vault story entry | Functional |
| [[STORY-020-Contract-Propose]] | `contract_propose` node: story-to-technical-contract generation | Functional |
| [[STORY-021-Contract-Validate]] | `contract_validate` node: DoD coverage check & contract merge | Functional |
| [[STORY-022-TOML-Routing]] | TOML per-node routing for all new pipeline nodes | Technical |
| [[STORY-023-Graph-Rewiring]] | `build_graph` rewiring: insert subflows before `plan` | Technical |

## Known Design Issues in the Original Proposal (addressed in child stories)

| Issue | Child Story | Resolution |
|-------|-------------|------------|
| `story_draft` used as **both** node name and `RunState` key | [[STORY-015-RunState-Story-Contract-Lifecycle]] | `RunState` key renamed to `story_text`; node name stays `story_draft` |
| `contract` key overloading — static AGENTS.md vs. dynamic output | [[STORY-015-RunState-Story-Contract-Lifecycle]], [[STORY-021-Contract-Validate]] | `contract_proposal` staged separately; merged into `contract` only after `contract_validate` passes |
| `rvc_link` write capability unspecified | [[STORY-019-RVC-Link]] | Explicit AC on `rvc create` CLI command + output parsing |
| Missing routing condition — when does Storywriter activate? | [[STORY-023-Graph-Rewiring]] | Conditional entry edge on `issue_id` absence or explicit `storywriter_mode` flag |
| Proposal uses single `worker_for(\"storywriter\")` for all story nodes | [[STORY-022-TOML-Routing]] | Per-node TOML routing keys: `story_research`, `story_draft`, `story_review`, `contract_propose`, `contract_validate` |
| `story_review_feedback`, `contract_gaps`, `contract_retries`, `storywriter_mode` missing from state schema | [[STORY-015-RunState-Story-Contract-Lifecycle]] | All 4 keys added to `RunState` table in STORY-015 AC |

## Definition of Done (Epic Level)

1. All 9 child stories are accepted.
2. The full pipeline flow diagram above executes end-to-end on the `adlai` project.
3. `state["contract"]` received by `plan_node` reflects the dynamically created contract when the Storywriter path ran, and still falls back to AGENTS.md when it did not.
4. No regression in any existing pipeline node (`plan`, `review`, `approve`, `act`, `qa`, `commit`).
5. All new nodes emit structured `history` events consistent with the existing [`_log()`](../../conductor/pipeline.py:89) pattern.

## Verification (Epic Gate)

1. Run `conductor run adlai "test task" --storywriter-mode always` end-to-end on the `adlai` project — all 6 new nodes appear in `state["history"]` in order: `story_research`, `story_draft`, `story_review`, `rvc_link`, `contract_propose`, `contract_validate`
2. Run `conductor run adlai "test task" --storywriter-mode off` — `history` contains no storywriter or contract nodes; pipeline reaches `plan_node` directly
3. `plan_node` receives `state["contract"]` equal to `contract_proposal` (not AGENTS.md content) when storywriter ran
4. `plan_node` receives original AGENTS.md content as `state["contract"]` when `storywriter_mode = "off"`
5. `cd TEAMFLOW/conductor && uv run conductor selftest adlai` — exits 0 (no regression in any existing node)
6. `cd TEAMFLOW/conductor && ruff check .` — no new errors introduced by any of the 9 child stories
