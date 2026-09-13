---
id: STORY-020
type: story
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags: ["pipeline", "contract", "planning"]
epic: "[[EPIC-003-Storywriter-Contract-Pipeline]]"
---

# STORY-020: `contract_propose` Node — Story-to-Technical-Contract Generation

**Epic**: [[EPIC-003]]
**Type**: Functional Story

---

As a **pipeline operator**,
I want Conductor to automatically derive a task-specific technical contract
from the finalized story,
So that the `plan_node` and `act_node` operate against a precise, run-scoped
contract that reflects this story's Definition of Done rather than the generic
static `AGENTS.md`.

---

## Acceptance Criteria

1. A `contract_propose_node` function is defined inside `build_graph` in
   [`pipeline.py`](../../conductor/pipeline.py:210).

2. The node resolves its worker via `cfg.worker_for("contract_propose")`.

3. The prompt passed to the worker includes all of:
   - `state["contract"]` (the current AGENTS.md — project-level baseline)
   - `state["story_text"]` (the finalized story)
   - `state["story_research_ctx"]` (codebase impact from STORY-016)
   - If `state["contract_valid"] == False` (retry path): the validation
     feedback stored in `state.get("contract_gaps", "")` must be included
     with a prominent label

4. The prompt instructs the worker to produce a **contract document** in
   AGENTS.md style containing all of:
   - An explicit **Definition of Done** section sourced directly from the
     story's DoD items
   - File/module restrictions (`DO NOT TOUCH` patterns)
   - Coding conventions relevant to the changed area
   - Testing requirements drawn from the story's Acceptance Criteria

5. On success, `state["contract_proposal"]` is populated with the worker's
   output text.

6. On worker failure (`res.ok == False`):
   - If this is the **first attempt**: store the AGENTS.md content as a
     fallback in `contract_proposal` and log a warning
   - If this is a **retry**: retain the previous `contract_proposal` and
     log an error. The node does NOT raise.

7. Raw stdout → `_save_raw_stdout()`, prompt → `_save_prompt()`.

8. A `history` event `"contract_propose"` is appended with fields `worker`,
   `ok`, `cmd`, `retry` (bool: `contract_valid == False` on entry).

9. Returned state keys: `contract_proposal`, `contract_valid` (reset to
   `False` to force re-validation), `status` (set to
   `"contract_validating"`), `history`.

---

## Edge Cases & Considerations

- **`contract_valid` reset**: every entry into `contract_propose_node` must
  reset `contract_valid = False` so `contract_validate_node` always runs a
  fresh check. This prevents a stale True from bypassing validation on retry.
- **Output format**: unlike `plan_node`, the output here is freeform markdown,
  not JSON. There is no schema to parse — the full `res.text` is stored.
- **Length guard**: if `res.text` exceeds `50_000` characters, log a warning.
  The existing AGENTS.md content (reference size ~2–10 KB for adlai) should
  guide the expected ceiling.
- **Critical design clarification**: the original proposal's `contract_proposal`
  is a *staging* contract. It does NOT replace `state["contract"]` at this
  node. Replacement only happens in STORY-021 after validation passes.
- **No RVC write here**: this node does not touch the vault. The contract is
  pipeline-internal until STORY-021 confirms it is valid.

---

## Dependencies

- STORY-015 (`contract_proposal`, `contract_valid` keys in `RunState`)
- STORY-019 (`rvc_link` node precedes this in the graph)
- STORY-022 (TOML routing for `contract_propose` worker)
- STORY-023 (graph edge: `rvc_link → contract_propose`)

---

## Definition of Done

- `contract_propose_node` is defined as a closure inside `build_graph` in [`pipeline.py`](../../conductor/pipeline.py)
- Worker resolved via `cfg.worker_for("contract_propose")`
- `contract_valid` is always reset to `False` on node entry (prevents stale bypass on retry)
- Prompt includes `contract` (AGENTS.md baseline), `story_text`, `story_research_ctx`; on retry (`contract_valid == False` at entry) also includes `contract_gaps`
- First-attempt worker failure: AGENTS.md content stored as fallback in `contract_proposal`; warning logged
- Retry worker failure: prior `contract_proposal` value retained; error logged; no exception raised
- Length guard: `len(res.text) > 50_000` → warning emitted (no exception)
- `history` event `"contract_propose"` appended with fields: `worker`, `ok`, `cmd`, `retry`

## Verification

1. Unit test — success, first attempt: `state["contract_proposal"] == res.text`, `state["contract_valid"] == False`, `state["status"] == "contract_validating"`
2. Unit test — failure, first attempt: `state["contract_proposal"] == state["contract"]` (AGENTS.md fallback)
3. Unit test — retry path with `contract_gaps`: `state["contract_valid"] = False, state["contract_gaps"] = "missing test coverage"` → assert `"missing test coverage"` appears in captured prompt
4. Unit test — failure on retry: `state["contract_proposal"]` retains prior value; no exception raised
5. Unit test — length guard: inject `res.text` of 51,000 characters → warning emitted, `contract_proposal` still populated
