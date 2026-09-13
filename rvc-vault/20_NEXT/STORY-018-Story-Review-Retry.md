---
id: STORY-018
type: story
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags: ["pipeline", "storywriter", "hitl", "planning"]
epic: "[[EPIC-003-Storywriter-Contract-Pipeline]]"
---

# STORY-018: `story_review` Node — Validation, Retry Loop & HitL Escalation

**Epic**: [[EPIC-003]]
**Type**: Functional Story

---

As a **pipeline operator**,
I want the drafted story to be automatically validated and iteratively improved
up to two times before requiring human intervention,
So that only well-formed, complete stories proceed to contract creation, while
I remain in control when automation cannot self-correct.

---

## Acceptance Criteria

1. A `story_review_node` function is defined inside `build_graph` in
   [`pipeline.py`](../../conductor/pipeline.py:210).

2. The node resolves its worker via `cfg.worker_for("story_review")`.

3. The worker is prompted to act as a strict reviewer and evaluate
   `state["story_text"]` against all of:
   - Presence of **Title**, **As a / I want / So that**, **Acceptance Criteria**
     (≥ 2 items), and **Definition of Done** (≥ 1 item)
   - Alignment of the story with `state["task"]` (no scope drift)
   - Internal consistency (no contradictory acceptance criteria)
   - The worker must emit a structured response:
     ```
     VERDICT: PASS | FAIL
     FEEDBACK: <specific gaps if FAIL, empty string if PASS>
     ```

4. **On PASS** (`VERDICT: PASS` detected in worker output):
   - `state["story_finalized"]` is set to `True`
   - `state["status"]` is set to `"story_finalized"`
   - The conditional edge in the graph routes to `rvc_link`

5. **On FAIL with `story_retries < 2`**:
   - `state["story_retries"]` is incremented by 1
   - `state["story_review_feedback"]` is populated with the `FEEDBACK:` section
   - `state["status"]` is set to `"story_drafting"`
   - The conditional edge routes back to `story_draft_node`

6. **On FAIL with `story_retries >= 2`** (retry ceiling hit):
   - The node calls LangGraph's `interrupt()` (same mechanism as
     [`approve_node`](../../conductor/pipeline.py:322)) with payload:
     ```python
     {
         "type": "story_review_request",
         "story_text": state["story_text"],
         "feedback": state.get("story_review_feedback", ""),
         "note": "Auto-review failed after 2 retries. Provide revised story text or 'skip' to bypass.",
     }
     ```
   - On resume with `{"story_text": "<revised>"}`: overwrite `state["story_text"]`,
     reset `story_retries` to `0`, route back to `story_draft_node`
   - On resume with `{"skip": true}`: set `story_finalized = True`, bypass
     further review, route directly to `rvc_link`

7. The retry ceiling (`2`) is **not hardcoded** — it reads from
   `cfg.max_story_retries` (new field added in STORY-022). Defaults to `2`.

8. Raw stdout → `_save_raw_stdout()`, prompt → `_save_prompt()`.

9. A `history` event `"story_review"` is appended with fields `worker`, `ok`,
   `verdict`, `retries`, `hitl` (bool).

10. Returned state keys vary by path (see above); all paths return `history`.

---

## Edge Cases & Considerations

- **Worker fails to emit structured `VERDICT:`**: treat as `FAIL` with
  feedback `"reviewer did not produce structured output"`. Do not treat a
  parse failure as a PASS.
- **HitL `skip` option**: necessary for cases where the task is inherently
  informal (e.g. quick hotfixes). The skip path marks `story_finalized = True`
  but does NOT create a contract (the contract phase can similarly be skipped
  — that routing decision belongs to STORY-023).
- **`story_review_feedback` key**: this key is not listed in the original
  proposal's state table (§3). It must be added to `RunState` as part of
  STORY-015 with type `str`.
- **Retry ceiling mirrors existing pattern**: `max_qa_retries: int = 2` on
  [`ProjectConfig`](../../conductor/projects_config.py:26) — a new `max_story_retries`
  field on `ProjectConfig` follows the same dataclass pattern.

---

## Dependencies

- STORY-015 (`story_text`, `story_retries`, `story_finalized`, +
  `story_review_feedback` added here)
- STORY-017 (`story_text` populated before this node runs)
- STORY-022 (TOML routing for `story_review`; `max_story_retries` config)
- STORY-023 (conditional edge: PASS → `rvc_link`, FAIL → `story_draft`,
  HitL → `interrupt()` + resume)

---

## Definition of Done

- `story_review_node` is defined as a closure inside `build_graph` in [`pipeline.py`](../../conductor/pipeline.py)
- Worker resolved via `cfg.worker_for("story_review")`
- PASS path: `story_finalized = True`, `status = "story_finalized"`, graph routes to `rvc_link`
- FAIL path (retries < ceiling): `story_retries` incremented, `story_review_feedback` populated from `FEEDBACK:` section, graph routes to `story_draft`
- HitL path (retries ≥ `cfg.max_story_retries`): `interrupt()` called with correct payload; both resume variants handled (`story_text` override and `skip`)
- Unstructured/unparseable worker output (no `VERDICT:` prefix) treated as FAIL — never as PASS
- Retry ceiling read from `cfg.max_story_retries` (not hardcoded)
- `history` event `"story_review"` appended with fields: `worker`, `ok`, `verdict`, `retries`, `hitl`

## Verification

1. Unit test — PASS verdict: `res.text` contains `"VERDICT: PASS"` → `story_finalized == True`, `status == "story_finalized"`, `history[-1]["verdict"] == "PASS"`
2. Unit test — FAIL, `story_retries=0`: → `story_retries == 1`, `story_review_feedback` contains the `FEEDBACK:` section content
3. Unit test — FAIL at ceiling (`story_retries=2`, `cfg.max_story_retries=2`): → `interrupt()` called; verify payload `type == "story_review_request"`
4. Unit test — resume with `{"story_text": "revised story"}`: → `state["story_text"] == "revised story"`, `story_retries == 0`
5. Unit test — resume with `{"skip": true}`: → `story_finalized == True`, routed to `rvc_link`
6. Unit test — garbled output (no `VERDICT:` prefix): → treated as FAIL, `story_retries` incremented, NOT as PASS
