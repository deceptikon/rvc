---
id: STORY-034
title: "rvc CLI hardening: false success, unscoped commits, plate write, triage proposals"
type: story
priority: P1
created: 2026-09-17
domain: workflow_meta
domain_tags: ["rvc", "cli", "bug", "triage", "plate", "git"]
epic: "[[EPIC-001-RVC-Protocol]]"
origin: "FEEDBACK-rvc.md (2026-09-17) — four live defects/hardening asks from a single transition session"
related:
  - "[[STORY-027-Transition-commits-should-skip-ci]]"
  - "[[STORY-028-rvc-create-mints-no-id-field]]"
  - "[[STORY-029-This-vault-violates-its-own-constitution]]"
  - "[[STORY-031-rvc-plate-drops-40-DECIDE-stories]]"
---

# STORY-034: rvc CLI Hardening

**Origin:** Four defects/hardening asks observed in a single transition session on 2026-09-17,
documented in `00_INBOX/FEEDBACK-rvc.md`. All four are live on the current `rvc-cli.py` and affect
core trust in the tool.

## Defect 1 — False success on unresolvable handle

`rvc issue PROPOSAL supersede` printed `[RVC] Issue PROPOSAL moved to superseded` and
`[RVC] Committing state...`, but **nothing moved and no commit was created**. The target file is
`type: proposal` with no `id:` field, so the ID lookup matched zero files. The CLI reported success
on a no-op.

**Why it matters:** A false green is worse than a crash. The operator trusts the bucket state and
walks away — only to discover later that nothing happened. The hand-fix required a manual `git mv`
(`3645eb9`).

**Fix:** Resolve the handle to an actual file **before** printing any transition line. If no file
matches, exit non-zero with a clear message: `no issue matches <handle>`. Never print "moved" or
"committing" until the move has actually succeeded.

## Defect 2 — Bare `git commit` sweeps unrelated staged index

The deferred commit for the same transition landed *after* the operator had released the index lock.
The bare `git commit` (no `-- <path>` scoping) then captured whatever was staged at that moment:
48 lines of `DECISIONS.md` and the feedback file ended up under the message
`rvc: Issue PROPOSAL -> superseded [skip ci]`.

**Why it matters:** Silent index corruption — unrelated work gets committed under an unrelated
message. This is a data-integrity violation.

**Fix (two-part):**
1. Scope the commit to the moved path only: `git commit -- <moved-path>`.
2. Never commit an index the CLI did not stage itself. Either use a temporary index or
   `git stash` / restore the original state around the commit.

## Defect 3 — `rvc plate` renders to stdout but cannot write `PLATE.md`

The constitution declares `PLATE.md` "a rendering, not a record … must be rebuildable from the
tree alone", yet nothing actually rebuilds it. After today's transitions it silently disagrees with
the tree, and only a hand-edit can refresh it — which is the one thing the rule forbids.

**Why it matters:** A plate that rots is worse than no plate; it becomes a source of truth that
lies. The constitution's intent (rebuildable, never hand-edited) is only enforceable if the tool
can write it.

**Fix:** Add `rvc plate --write` (or auto-write on any transition) so the rendering can be
refreshed from the tree at any time. The `--write` flag should be explicit to avoid accidental
overwrites; auto-write on transition is a secondary ask.

## Defect 4 — Proposal type has no triage target

`40_DECIDE` is defined as "one question per file, with a block: decision needed · options ·
recommendation · default if unanswered" — a design proposal with an action checklist does not fit
that shape, yet `PROPOSAL` files sat there for four days. If `00_INBOX` deposits of `type: proposal`
have no valid transition target, `rvc` should say so at triage time rather than leave them to rot.

**Why it matters:** Triage silently deposits proposals into the wrong bucket, creating the
appearance of progress while the item rots. The tool should be honest about what it can and cannot
route.

**Fix:** During `rvc issue <ID> triage` (or `rvc triage`), when the file's `type:` is `proposal`
and no bucket mapping exists for that type, emit a warning: `type 'proposal' has no triage target —
manual placement required`. Exit non-zero or print the warning to stderr so the operator knows to
place it by hand.

---

## Acceptance Criteria

- [ ] **AC 1: False success eliminated**
  `rvc issue <ID> <verb>` exits non-zero with `no issue matches <handle>` when the handle resolves
  to no file. No transition or commit messages are printed before the error.

- [ ] **AC 2: Commit scoped to moved path**
  Transition commits use `git commit -- <moved-path>` (or equivalent path-scoped mechanism) so
  only the moved file is committed. Unstaged work in the index is never captured.

- [ ] **AC 3: `rvc plate --write` persists the rendering**
  `rvc plate --write` writes `10_CONTEXT/PLATE.md` from the tree. `rvc plate` (no flag) continues
  to print to stdout unchanged. The written file is identical to stdout output.

- [ ] **AC 4: Triage warns on untriageable types**
  `rvc triage` (or `rvc issue <ID> triage`) prints a stderr warning when `type:` has no bucket
  mapping, and does not move the file. The operator is told to place it manually.

- [ ] **AC 5: FEEDBACK-rvc.md consumed**
  `00_INBOX/FEEDBACK-rvc.md` is superseded (moved to `90_ARCHIVE/superseded`) once all four ACs
  pass.

---

## Definition of Done

- All four ACs pass.
- Regression tests cover: (a) unresolvable handle exits non-zero, (b) commit does not sweep
  staged index, (c) `plate --write` produces correct output, (d) triage warns on `type: proposal`.
- `10_CONTEXT/DECISIONS.md` updated with the fix decisions.
- `00_INBOX/FEEDBACK-rvc.md` moved to `90_ARCHIVE/superseded`.
