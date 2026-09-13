---
id: STORY-015
type: story
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags: ["planning", "pipeline", "statemanagement"]
epic: "[[EPIC-003-Storywriter-Contract-Pipeline]]"
---

# STORY-015: Extend `RunState` with Story & Contract Lifecycle Fields

**Epic**: [[EPIC-003]]
**Type**: Technical Story

---

As a **pipeline developer**,
I want to add the story and contract lifecycle fields to [`RunState`](../../conductor/pipeline.py:60),
So that all new Storywriter and Contract Creation nodes have a typed, durable
state ledger consistent with the existing checkpoint pattern.

---

## Acceptance Criteria

1. The following keys are added to [`RunState`](../../conductor/pipeline.py:60) (all `total=False` — optional):

   | Key | Type | Purpose |
   |-----|------|---------|
   | `story_research_ctx` | `str` | Output of the `story_research` node: codebase & RVC impact summary |
   | `story_text` | `str` | Current narrative story content (replaces the ambiguous `story_draft` key name from the original proposal) |
   | `story_retries` | `int` | Number of `story_draft`→`story_review` iterations so far (mirrors `qa_attempts` pattern) |
   | `story_finalized` | `bool` | True once `story_review` accepts the story; gates entry into `rvc_link` |
   | `rvc_story_id` | `str` | The RVC issue ID created by `rvc_link` (e.g. `STORY-91`); written back to `issue_id` if not already set |
   | `contract_proposal` | `str` | Dynamically generated technical contract from `contract_propose` node |
   | `contract_valid` | `bool` | True once `contract_validate` accepts `contract_proposal` |
   | `story_review_feedback` | `str` | Reviewer feedback text from `story_review_node` on FAIL; injected into the retry prompt by `story_draft_node` (see STORY-018) |
   | `contract_gaps` | `str` | Unaddressed DoD items from `contract_validate_node`'s `GAPS:` output; passed back to `contract_propose_node` on retry (see STORY-021) |
   | `contract_retries` | `int` | Number of `contract_propose→contract_validate` loop iterations; guards against infinite loop (see STORY-021) |
   | `storywriter_mode` | `str` | Entry-condition switch: `"auto"` (default) \| `"always"` \| `"off"` — controls Storywriter subflow activation (see STORY-023) |

2. The **existing** `contract: str` key is **not removed or renamed**; it continues to hold the AGENTS.md content read at graph entry and is overwritten with `contract_proposal` only after `contract_valid` is True (enforced in STORY-021, not here).

3. All new keys include an inline comment matching the style of existing keys in [`RunState`](../../conductor/pipeline.py:60).

4. No existing node (`plan_node`, `act_node`, etc.) references the new keys; adding them is purely additive.

5. `story_retries` uses `int` (not `bool`) to mirror the well-established `qa_attempts: int` + `max_qa_retries` retry-ceiling pattern from [`pipeline.py:418`](../../conductor/pipeline.py:418).

---

## Edge Cases & Considerations

- **Naming conflict resolved**: the original proposal used `story_draft` as both a node name and a state key. This story uses `story_text` for the state key. The node function is named `story_draft_node` internally and registered as `"story_draft"` in the graph.
- **`rvc_story_id` vs `issue_id`**: If the caller already supplied `issue_id`, `rvc_link` must NOT overwrite it. `rvc_story_id` stores the newly created ID separately; `issue_id` propagation is decided in STORY-019.
- **Security**: No credentials or vault tokens are stored in `RunState`; those remain in environment variables.

---

## Dependencies

None — this is the first story in the epic and has no upstream dependencies.

---

## Definition of Done

- All 11 new `RunState` keys (7 lifecycle keys + `story_review_feedback`, `contract_gaps`, `contract_retries`, `storywriter_mode`) are present in [`pipeline.py`](../../conductor/pipeline.py) with correct type annotations and `total=False`
- All new keys have inline comments consistent with the style of existing `RunState` key comments
- No existing node function (`plan_node`, `act_node`, `review_node`, `approve_node`, `qa_node`, `commit_node`) imports or references any new key
- `ruff check .` passes on the modified [`pipeline.py`](../../conductor/pipeline.py) with zero new errors

## Verification

1. `python -c "from conductor.pipeline import RunState; keys = RunState.__annotations__; assert all(k in keys for k in ['story_research_ctx','story_text','story_retries','story_finalized','rvc_story_id','contract_proposal','contract_valid','story_review_feedback','contract_gaps','contract_retries','storywriter_mode'])"` — exits 0
2. Inspect annotated types: `story_retries: int`, `contract_retries: int`, `story_finalized: bool`, `contract_valid: bool`, `storywriter_mode: str`
3. `cd TEAMFLOW/conductor && uv run conductor selftest adlai` — exits 0 (no existing node regression)
4. `cd TEAMFLOW/conductor && ruff check .` — no new errors introduced
