---
id: STORY-016
type: story
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags: ["pipeline", "storywriter", "planning"]
epic: "[[EPIC-003-Storywriter-Contract-Pipeline]]"
---

# STORY-016: `story_research` Node — Codebase & RVC Impact Analysis

**Epic**: [[EPIC-003]]
**Type**: Functional Story

---

As a **pipeline operator submitting a task to Conductor**,
I want the pipeline to automatically scan the codebase and any existing RVC
context before drafting a story,
So that the subsequent story and plan are grounded in the actual code structure
and do not contradict existing architecture decisions.

---

## Acceptance Criteria

1. A `story_research_node` function is defined inside `build_graph` in
   [`pipeline.py`](../../conductor/pipeline.py:210), following the exact closure pattern of
   `plan_node` and the other existing nodes.

2. The node resolves its worker via `cfg.worker_for("story_research")`,
   enabling per-project TOML override (see STORY-022).

3. The prompt instructs the worker to operate **read-only** and produce a
   structured impact summary covering:
   - Which existing files/modules are likely affected
   - Relevant patterns, conventions, or constraints already in the codebase
   - A summary of any RVC context found for `state.get("issue_id")`

4. The node calls the existing `_rvc_context()` helper at
   [`pipeline.py:127`](../../conductor/pipeline.py:127) with `state.get("issue_id", "")` and
   `state.get("rvc_mode", "full")` — no new RVC read path is introduced.

5. The node calls `_git_context()` at [`pipeline.py:95`](../../conductor/pipeline.py:95) and
   includes the result in the prompt, exactly as `plan_node` does.

6. On success, `state["story_research_ctx"]` is populated with the worker's
   output text (raw `res.text`).

7. On worker failure (`res.ok == False`), the node **does not raise**; it
   stores a degraded context string (e.g. `"(research failed: <error>)"`) in
   `story_research_ctx` and logs an error, allowing the pipeline to continue
   into `story_draft` with reduced context.

8. Raw stdout is persisted via `_save_raw_stdout()` and the prompt via
   `_save_prompt()`, consistent with every other worker-backed node.

9. A `history` event `"story_research"` is appended via `_log()` with fields
   `worker`, `ok`, `cmd`, `ctx_len`.

10. Returned state keys: `story_research_ctx`, `status` (set to
    `"story_drafting"`), `history`.

---

## Edge Cases & Considerations

- **No `issue_id` supplied**: `_rvc_context()` returns `""` cleanly — the
  research node must still produce useful output from git context + task alone.
- **Large codebase**: worker timeout for this node should default to `300s`
  (lighter than `plan_node`'s `600s`) since it is read-only analysis.
- **Worker is read-only**: the TOML routing entry for `story_research` should
  set `read_only = true` by default (see STORY-022).
- **`story_research_ctx` reuse**: if `story_retries > 0`, the node must NOT
  re-run — the graph edge from `story_review` must route back to `story_draft`
  directly, bypassing `story_research`. The routing logic lives in STORY-023.

---

## Dependencies

- STORY-015 (`story_research_ctx` key in `RunState`)
- STORY-022 (TOML routing for `story_research` worker)
- STORY-023 (graph wiring to place this node at `START`)

---

## Definition of Done

- `story_research_node` is defined as a closure inside `build_graph` in [`pipeline.py`](../../conductor/pipeline.py), following the `plan_node` closure pattern
- Worker resolved strictly via `cfg.worker_for("story_research")`
- On worker failure (`res.ok == False`): `story_research_ctx` contains a degraded marker string, no exception propagates
- `_save_raw_stdout()` and `_save_prompt()` are called on every execution
- `history` event `"story_research"` appended with fields: `worker`, `ok`, `cmd`, `ctx_len`
- `uv run conductor selftest adlai` exits 0

## Verification

1. Unit test — success path: inject mock worker returning `res.ok=True, res.text="impact summary"` → assert `state["story_research_ctx"] == "impact summary"`, `state["status"] == "story_drafting"`
2. Unit test — failure path: inject mock worker returning `res.ok=False, res.error="timeout"` → assert `state["story_research_ctx"]` starts with `"(research failed:"`, no exception raised
3. Unit test — no `issue_id` in state: `_rvc_context()` returns `""`, node still produces non-empty `story_research_ctx` from git context + task
4. `cd TEAMFLOW/conductor && uv run conductor selftest adlai` — exits 0
