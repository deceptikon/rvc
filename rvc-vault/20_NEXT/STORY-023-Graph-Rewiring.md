---
id: STORY-023
type: story
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags: ["pipeline", "langgraph", "architecture", "planning"]
epic: "[[EPIC-003-Storywriter-Contract-Pipeline]]"
---

# STORY-023: `build_graph` Rewiring — Insert Subflows Before `plan`

**Epic**: [[EPIC-003]]
**Type**: Technical Story

---

As a **pipeline developer**,
I want `build_graph` in [`pipeline.py`](../../conductor/pipeline.py:210) to wire the new
Storywriter and Contract Creation nodes into the `StateGraph` with correct
conditional edges, entry conditions, and retry/HitL routing,
So that the full integrated pipeline runs as a coherent, resumable LangGraph
with no regressions in the existing post-planning nodes.

---

## Acceptance Criteria

### A. Entry Condition — When Does Storywriter Run?

1. A new input key `storywriter_mode: str` is added to `RunState` (via
   STORY-015), defaulting to `"auto"`. Values:
   - `"auto"` — run Storywriter if `issue_id` is not set
   - `"always"` — always run Storywriter
   - `"off"` — skip directly to `plan` (preserves legacy behaviour)

2. The `START` edge is replaced with a **conditional entry edge** that
   inspects `state.get("storywriter_mode", "auto")` and
   `state.get("issue_id", "")`:
   - `"off"` → `plan`
   - `"always"` → `story_research`
   - `"auto"` + `issue_id == ""` → `story_research`
   - `"auto"` + `issue_id != ""` → `plan`

   This conditional replaces the plain `graph.add_edge(START, "plan")` that
   currently exists in `build_graph`.

### B. Storywriter Subflow Edges

3. `graph.add_edge("story_research", "story_draft")` — unconditional.

4. `graph.add_conditional_edges("story_draft", ...)` — always routes to
   `"story_review"` (no branching at draft).

5. `graph.add_conditional_edges("story_review", _story_review_router)` where
   `_story_review_router(state)` returns:
   - `"rvc_link"` if `state.get("story_finalized")`
   - `"story_draft"` if `story_retries < cfg.max_story_retries` (routes back with feedback)
   - `"__interrupt__"` if `story_retries >= cfg.max_story_retries` (triggers `interrupt()` inside the node — NOT a separate graph node)

   > Note: the HitL is implemented as `interrupt()` **inside** `story_review_node`,
   > consistent with how `approve_node` works at [`pipeline.py:331`](../../conductor/pipeline.py:331).
   > There is no separate `HitL_Story` graph node.

6. `graph.add_edge("rvc_link", "contract_propose")` — unconditional.

### C. Contract Creation Subflow Edges

7. `graph.add_conditional_edges("contract_propose", ...)` — always routes to
   `"contract_validate"`.

8. `graph.add_conditional_edges("contract_validate", _contract_validate_router)`
   where `_contract_validate_router(state)` returns:
   - `"plan"` if `state.get("contract_valid")`
   - `"contract_propose"` if `contract_retries < cfg.max_contract_retries`
   - `"__interrupt__"` if `contract_retries >= cfg.max_contract_retries`
     (HitL inside `contract_validate_node`)

### D. Existing Edges — Preserved Unchanged

9. All edges from `plan` onward remain exactly as they are today:
   ```
   plan → review → approve → (act|rejected) → qa → (act|plan_reviser) → commit → END
   ```
   No existing `add_edge` or `add_conditional_edges` call is removed or
   modified.

### E. Node Registration

10. All five new node functions are registered with `graph.add_node(...)`:
    ```python
    graph.add_node("story_research",   story_research_node)
    graph.add_node("story_draft",      story_draft_node)
    graph.add_node("story_review",     story_review_node)
    graph.add_node("rvc_link",         rvc_link_node)
    graph.add_node("contract_propose", contract_propose_node)
    graph.add_node("contract_validate",contract_validate_node)
    ```

### F. Regression Gate

11. An integration test (or a documented manual smoke-test) must pass that
    runs the pipeline end-to-end with `storywriter_mode = "off"` and verifies
    the pipeline behaves identically to the pre-epic version.

12. An integration test runs with `storywriter_mode = "always"` and verifies
    `state["contract"]` is replaced before `plan_node` receives it.

---

## Edge Cases & Considerations

- **LangGraph `interrupt()` vs. graph nodes**: the original proposal drew
  `HitL_Story[Human Intervention]` as a separate Mermaid node, implying a
  separate graph node. In reality, LangGraph's `interrupt()` pauses the graph
  **inside** the calling node and resumes there. Adding a separate graph node
  would be incorrect. This story corrects that misunderstanding.
- **`storywriter_mode` default is `"auto"`**: this means existing callers that
  do not pass `issue_id` will silently activate Storywriter after this story
  is deployed. Callers that want the old behaviour must pass
  `storywriter_mode = "off"` explicitly. This is a **breaking change** for
  callers that omit `issue_id`. Must be communicated in a release note.
- **Checkpoint compatibility**: adding new `RunState` keys is backward-
  compatible with existing SQLite checkpoints (LangGraph `TypedDict total=False`
  allows missing keys). Adding new graph nodes changes the graph topology,
  which may invalidate in-flight checkpoints. Existing in-progress runs should
  be drained before deploying this story.
- **`_story_review_router` and `_contract_validate_router` placement**: these
  router functions must be defined as closures inside `build_graph` (like all
  other conditional edge lambdas) to capture `cfg`.

---

## Dependencies

- STORY-015 (all new `RunState` keys, including `storywriter_mode`)
- STORY-016 through STORY-021 (all node functions must exist before wiring)
- STORY-022 (`cfg.max_story_retries`, `cfg.max_contract_retries` used by routers)

---

## Definition of Done

- All 6 new nodes registered in `build_graph` via `graph.add_node(...)`
- `START → plan` plain edge replaced with a conditional entry edge covering all 4 `storywriter_mode` + `issue_id` combinations
- `_story_review_router` and `_contract_validate_router` defined as closures inside `build_graph` (capture `cfg`)
- All existing edges from `plan` onward are unmodified (verified by regression gate)
- Regression test passes: `storywriter_mode = "off"` → pipeline behaviour identical to pre-epic (no storywriter nodes in `history`)
- Integration test passes: `storywriter_mode = "always"` → `state["contract"]` replaced before `plan_node` receives it

## Verification

1. Unit test — `_story_review_router(state)` with `story_finalized=True`: → returns `"rvc_link"`
2. Unit test — `_story_review_router(state)` with `story_finalized=False, story_retries=1, cfg.max_story_retries=2`: → returns `"story_draft"`
3. Unit test — `_contract_validate_router(state)` with `contract_valid=True`: → returns `"plan"`
4. Regression test: `conductor run adlai "fix lint" --storywriter-mode off` → `history` contains no `"story_research"`, `"story_draft"`, or `"story_review"` events
5. Integration test: `storywriter_mode = "always"` → `history` contains events for all 6 new nodes in order: `story_research`, `story_draft`, `story_review`, `rvc_link`, `contract_propose`, `contract_validate`
6. `cd TEAMFLOW/conductor && uv run conductor selftest adlai` — exits 0
