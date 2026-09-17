---
type: feedback
tags: [rvc, feedback]
---

# FEEDBACK — rvc

- **2026-09-17 — `rvc issue <ID> <verb>` reports success on a no-op when the handle resolves to no file.**
  `rvc issue PROPOSAL supersede` printed `[RVC] Issue PROPOSAL moved to superseded (90_ARCHIVE/superseded)`
  and `[RVC] Committing state...`, but nothing moved and no commit was created — the target file is
  `type: proposal` with no `id:` field, so the ID lookup matched nothing. A false green is worse than an
  error: I would have trusted the bucket. Ask: resolve the handle first and exit non-zero with
  "no issue matches <handle>", before printing any transition line. (Moved by hand in `3645eb9`.)
- **2026-09-17 — that same transition committed later, sweeping an unrelated staged index.** Its commit
  landed after mine had released the index lock, and the bare `git commit` then took whatever was staged
  at that moment: 48 lines of `DECISIONS.md` + this file ended up under the message
  `rvc: Issue PROPOSAL -> superseded [skip ci]`. Two asks: scope the commit to the moved path
  (`git commit -- <path>`), and never commit an index you did not stage.
- **2026-09-17 — `rvc plate` renders to stdout but cannot write `10_CONTEXT/PLATE.md`.** The
  constitution makes `PLATE.md` "a rendering, not a record … must be rebuildable from the tree alone",
  yet nothing rebuilds it: after today's transitions it disagrees with the tree and only a hand-edit can
  refresh it, which is the one thing the rule forbids. Ask: `rvc plate --write` (or auto-write on any
  transition) so the rendering cannot silently rot.
- **2026-09-17 — the bucket a proposal belongs in has no name in the tree.** `40_DECIDE` is defined as
  "one question per file, with a block: decision needed · options · recommendation · default if
  unanswered" — a design proposal with an action checklist does not fit that shape, yet it sat there for
  four days. If `00_INBOX` deposits of type `proposal` have no transition target, `rvc` should say so at
  triage time rather than leave them to rot in the blocked bucket.
