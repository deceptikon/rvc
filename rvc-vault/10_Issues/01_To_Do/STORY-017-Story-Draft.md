---
id: STORY-017
type: story
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags: ["pipeline", "storywriter", "planning"]
epic: "[[EPIC-003-Storywriter-Contract-Pipeline]]"
---

# STORY-017: `story_draft` Node — Narrative Story Generation

**Epic**: [[EPIC-003]]
**Type**: Functional Story

---

As a **pipeline operator**,
I want Conductor to automatically generate a well-structured user story from
the research context and the raw task description,
So that downstream nodes (contract creation, planning) operate on a precise,
human-readable requirement rather than an ad-hoc task string.

---

## Acceptance Criteria

1. A `story_draft_node` function is defined inside `build_graph` in
   [`pipeline.py`](../../conductor/pipeline.py:210).

2. The node resolves its worker via `cfg.worker_for("story_draft")`.

3. The prompt passed to the worker MUST include all of:
   - `state["contract"]` (AGENTS.md — project conventions)
   - `state["story_research_ctx"]` (output of STORY-016)
   - `state["task"]` (the original task string)
   - If `state["story_retries"] > 0`: the reviewer's feedback from the
     previous iteration (stored as `state.get("story_review_feedback", "")`)

4. The prompt instructs the worker to produce a story in the standard format:
   ```
   Title: [Brief descriptive title]

   As a [specific user role/persona],
   I want to [clear action/goal],
   So that [tangible benefit/value].

   Acceptance Criteria:
   1. ...
   2. ...

   Definition of Done:
   - ...
   ```

5. On success, `state["story_text"]` is populated with the worker's output.

6. On worker failure, `story_text` retains its previous value (if a retry) or
   is set to `""`. The node logs a warning and does NOT raise.

7. Raw stdout → `_save_raw_stdout()`, prompt → `_save_prompt()`.

8. A `history` event `"story_draft"` is appended with fields `worker`, `ok`,
   `cmd`, `retry` (bool: `story_retries > 0`).

9. Returned state keys: `story_text`, `status` (set to `"story_reviewing"`),
   `history`.

10. Worker timeout defaults to `300s`.

---

## Edge Cases & Considerations

- **Empty research context**: if `story_research_ctx` is `""` or contains a
  degraded-context marker, the node must still attempt a draft using only
  `task` and `contract`.
- **Retry with feedback**: on the second or third attempt the prompt must
  clearly label the reviewer's feedback section so the model addresses it
  specifically. A generic retry without feedback context produces the same
  output and wastes the retry budget.
- **Idempotency**: the node does not check whether `story_text` already has
  content — it always overwrites. Idempotency is the graph's responsibility
  (routing from `story_review` back here on failure).

---

## Dependencies

- STORY-015 (`story_text`, `story_retries` keys)
- STORY-016 (`story_research_ctx` populated before this node runs)
- STORY-018 (defines `story_review_feedback` written back to state)
- STORY-022 (TOML routing for `story_draft` worker)
- STORY-023 (graph edge: `story_research → story_draft`)

---

## Definition of Done

- `story_draft_node` is defined as a closure inside `build_graph` in [`pipeline.py`](../../conductor/pipeline.py)
- Worker resolved via `cfg.worker_for("story_draft")`
- Prompt includes `contract`, `story_research_ctx`, and `task`; on retry (`story_retries > 0`) also includes `story_review_feedback`
- On worker failure, first attempt: `story_text == ""`; on retry: prior `story_text` value retained; no exception raised in either case
- `_save_raw_stdout()` and `_save_prompt()` called on every execution
- `history` event `"story_draft"` appended with fields: `worker`, `ok`, `cmd`, `retry`
- Worker timeout defaults to `300s`

## Verification

1. Unit test — success, first attempt: `res.ok=True, res.text="story content"` → `state["story_text"] == "story content"`, `state["status"] == "story_reviewing"`, `history[-1]["retry"] == False`
2. Unit test — success, retry: `state["story_retries"] = 1, state["story_review_feedback"] = "needs clearer AC"` → assert `"needs clearer AC"` appears in captured prompt
3. Unit test — failure, first attempt: `res.ok=False` → `state["story_text"] == ""`, no exception
4. Unit test — failure, retry (`story_retries=1`): `state["story_text"] = "prior draft"`, `res.ok=False` → `state["story_text"]` remains `"prior draft"`
5. `cd TEAMFLOW/conductor && uv run conductor selftest adlai` — exits 0
