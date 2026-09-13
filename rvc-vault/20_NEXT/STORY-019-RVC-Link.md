---
id: STORY-019
type: story
status: To Do
priority: High
started: 2026-07-03
domain: workflow_meta
domain_tags: ["pipeline", "rvc", "planning"]
epic: "[[EPIC-003-Storywriter-Contract-Pipeline]]"
---

# STORY-019: `rvc_link` Node — Create & Link RVC Vault Story Entry

**Epic**: [[EPIC-003]]
**Type**: Functional Story

---

As a **pipeline operator**,
I want Conductor to automatically create a traceable story entry in the RVC
vault once a story is finalized,
So that every pipeline run that produces code changes has an auditable,
linked requirement record in the project vault without manual vault editing.

---

## Acceptance Criteria

1. A `rvc_link_node` function is defined inside `build_graph` in
   [`pipeline.py`](../../conductor/pipeline.py:210).

2. The node is **not worker-backed** — it invokes the `rvc` CLI directly
   (same pattern as `_rvc_context()` at [`pipeline.py:127`](../../conductor/pipeline.py:127)
   and `commit_node`'s `subprocess.run` at [`pipeline.py:514`](../../conductor/pipeline.py:514)).

3. The node calls `rvc create --title "<first line of story_text>"` (or
   equivalent write subcommand confirmed against the installed `rvc` CLI).
   The exact command is discovered by running `rvc --help` during implementation.

4. On success, the stdout of `rvc create` is parsed to extract the new issue
   ID (e.g. `STORY-91`). This ID is written to `state["rvc_story_id"]`.

5. **If `state.get("issue_id")` is already set** (caller supplied an existing
   RVC issue): the node skips creation and writes the story text as a comment
   or sub-note on the existing issue instead (using `rvc comment <issue_id>`
   or equivalent). `rvc_story_id` is set to the pre-existing `issue_id`.

6. **If `rvc` binary is not found** (same fallback logic as
   [`pipeline.py:139`](../../conductor/pipeline.py:139)): the node logs a warning and
   sets `rvc_story_id = ""`. The pipeline continues — `rvc_story_id` being
   empty is a non-fatal degraded state.

7. After writing, the node calls `_rvc_context()` once more with the new
   `rvc_story_id` (mode `"get"`) to confirm the entry exists, and appends
   the result to `state["story_research_ctx"]` (so downstream nodes have the
   canonical vault link).

8. A `history` event `"rvc_link"` is appended with fields `rvc_story_id`,
   `skip_reason` (empty string if creation ran, `"issue_id_exists"` if
   pre-existing), `ok`.

9. Returned state keys: `rvc_story_id`, `story_research_ctx`,
   `status` (set to `"contract_proposing"`), `history`.

---

## Edge Cases & Considerations

- **`rvc create` idempotency**: if the same title already exists in the vault,
  `rvc create` may return an error. The node must detect this case (non-zero
  exit + duplicate-title error text) and reuse the existing ID rather than
  failing.
- **Story text length**: `rvc create` may have a title length limit. The node
  truncates to the first 80 characters of the first line of `story_text`.
- **Critical gap from original proposal**: the original proposal references
  `rvc_link` as "creates the RVC story entry and establishes linking" but
  does not specify the CLI command. This story fills that gap by requiring
  implementation discovery via `rvc --help`. If `rvc create` does not exist,
  the implementer must open a sub-task against the `rvc` CLI team.
- **Existing `_rvc_context()` is read-only**: this node introduces the first
  **write** operation to the RVC vault. It must be explicitly documented in
  the code as a side-effecting node (comment: `# RVC WRITE OPERATION`).

---

## Dependencies

- STORY-015 (`rvc_story_id` key in `RunState`)
- STORY-018 (`story_finalized = True` gates entry to this node)
- STORY-023 (graph edge: `story_review` PASS → `rvc_link`)

---

## Definition of Done

- `rvc_link_node` is defined as a closure inside `build_graph` — NOT worker-backed; uses `subprocess.run` / `rvc` CLI directly
- Creation path: `rvc create` stdout parsed to extract new issue ID into `state["rvc_story_id"]`
- Pre-existing `issue_id` path: `rvc comment <id>` used instead; `rvc_story_id` set to pre-existing ID
- Missing `rvc` binary: `rvc_story_id = ""`, pipeline continues without exception (non-fatal degraded state)
- Duplicate-title detected: existing ID reused, no error raised
- `# RVC WRITE OPERATION` comment present in source immediately before the node definition
- Post-write confirmation: `_rvc_context()` called once with new `rvc_story_id` (mode `"get"`)
- `history` event `"rvc_link"` appended with fields: `rvc_story_id`, `skip_reason`, `ok`

## Verification

1. Unit test — success, no prior `issue_id`: mock `rvc create` returning `"Created STORY-91"` → `state["rvc_story_id"] == "STORY-91"`, `state["status"] == "contract_proposing"`
2. Unit test — missing `rvc` binary: mock `subprocess.run` raising `FileNotFoundError` → `rvc_story_id == ""`, no exception raised
3. Unit test — pre-existing `issue_id = "STORY-88"`: → `rvc comment STORY-88` invoked (not `rvc create`), `rvc_story_id == "STORY-88"`
4. Unit test — duplicate title (non-zero exit + duplicate-title error text): → existing ID extracted, `rvc_story_id` set to that ID, no error raised
5. `grep -n "RVC WRITE OPERATION" TEAMFLOW/conductor/conductor/pipeline.py` — returns a match
