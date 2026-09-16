---
id: STORY-031
type: story
priority: P1
created: 2026-09-16
domain: workflow_meta
domain_tags: ["plate", "rvc", "bug", "cross-vault"]
origin: "ADLAI vault (Q, 2026-09-16) — found while diffing `rvc plate` against the folder tree"
related:
  - "[[STORY-024-Plate-lanes-are-protocol-not-local-law]]"
  - "[[STORY-030-Cross-vault-finding-delivery]]"
---

# STORY-031: `rvc plate` renders no `40_DECIDE` root stories

**Origin:** cross-vault finding from ADLAI — the channel [[STORY-030]] exists to make routine. Filed
by hand with an explicit `id:` because [[STORY-028]] is not landed; once `rvc report` exists, this
becomes the reference regression test for it.

## The defect

`rvc plate` (both text and `--format json`) drops a **blocked-decision story** whose file sits in
`40_DECIDE/` root. Only non-issue files from that bucket render (the registered waiting exception),
so an issue that is blocked on a ruling appears in **no lane at all**.

Reproduction, live 2026-09-16 on ADLAI's vault:

1. `rvc issue list` shows `STORY-113-…md [40_DECIDE]` — the tree scan sees it.
2. `rvc plate` shows `PROPOSAL--Cross-Dev-…md` (a non-issue, `is_issue: false`) in WAITING, but not
   STORY-113.
3. `rvc plate --format json` returns no lane containing STORY-113.

The lane-assignment branch for the decide bucket routes to `waiting` only when
`in_decide and not is_deliberation and not is_issue` — the final clause is what drops blocked stories.

## Why it matters

This vault's own lifecycle makes `40_DECIDE` the home of blocked decisions ("one question per file").
The plate's failure mode is the silent one — **a decision the owner is waiting on looks like it does
not exist** — which is exactly the class STORY-030 exists to eliminate (a tracker must not lie by
omission). The consuming vault's human DQL view (PLATE.md "Awaiting a ruling" lane) lists *all* of
`40_DECIDE`, so the two renderers already disagree about a P1 item today.

## Suggested fix

In the plate lane assignment, give `40_DECIDE` root a `waiting`/blocked lane for **issues** as well —
the fix is the `is_issue` clause. The v6.0 semantics ("blocked pending a ruling", flat, one question
per file) mean a story there is a first-class waiting item, not a deliberation.

## Acceptance criteria

1. A story (`type: story`) in `40_DECIDE/` root appears in `rvc plate` text and JSON output.
2. Existing behavior unchanged: proposals in `40_DECIDE` and deferred issues still render as today.
3. A regression test covers a blocked-decision story (belt: extend the plate tests; suspenders: the
   STORY-024 cross-renderer agreement fixture gains a `40_DECIDE` case so the DQL and the CLI cannot
   drift again).

## Notes

- ADLAI carries a one-line workaround in its GOTCHAS until this lands: after `rvc plate`, also list
  `40_DECIDE/` by hand. It will prune that line to a pointer at this issue when fixed.
- Triage me into `20_NEXT` when convenient — filed directly because the reporter has no `rvc report`
  yet and the defect is live.