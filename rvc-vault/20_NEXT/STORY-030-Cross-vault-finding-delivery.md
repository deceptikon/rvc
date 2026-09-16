---
id: STORY-030
type: story
priority: P2
created: 2026-09-16
domain: workflow_meta
domain_tags: ["protocol", "cross-vault", "feedback", "triage"]
---

# STORY-030: There is no way for a consuming vault to report a defect to RVC

---

## The incident this story exists for

ADLAI `STORY-107` closed on 2026-09-13 carrying a section titled **"Findings (S2 smoke-run, for
big-pickle)"** — three observations about `rvc`, addressed to a specific person, written as prose
inside a *closed ticket in a different git repository*. RVC's own vault had no way to see them.

What happened next is the interesting part:

- One finding (a wrong-inbox bug) **was fixed on 2026-09-14** — and nobody closed the finding. Three
  days later I re-verified it from scratch and it no longer reproduces, but the only way to know that
  was to run the reproduction myself. The defect is gone; the ticket that reported it still asserts it
  is live, in a vault whose tooling cannot see this one.
- The other two findings are still open and still have no owner here.
- The person the findings were addressed to had no mailbox for them.

**A bug report whose only address is a paragraph in someone else's closed issue is not a bug report.
It is a diary entry.** And the worst outcome isn't that the bug went unfixed — it's that a future
reader now has to re-run the experiment to find out whether their own tracker is lying to them.

## Acceptance criteria

1. `rvc` gains a way to file a finding against a *different* vault — something like
   `rvc report <target-vault> "<text>"`, which mints an issue in the target's `tree.create` bucket
   with `origin:` naming the source vault and the source issue id. Cross-vault, id-bearing, triageable.
2. **The origin is written on the finding as it arrives.** If the reporting vault ever compiles away
   the ticket that raised it, the receiving issue must still say who asked and why.
3. Closing a finding in one vault does not silently close it in the other; the receiving issue is the
   single source of truth for whether the defect is live. One fact, one folder — the same law this
   vault already applies to `status:`.
4. `rvc plate` grows an optional outbox/inbox lane for cross-vault findings, so a SYNC in either
   direction surfaces them without reading the other vault's files.

## Non-goals

- **Do not** solve this by letting vaults read each other's documents. ADLAI's owner ruled that
  TEAMFLOW's legacy surface "will burst your context and probably poison it," and that judgment is
  correct and should be respected as a design input: the transfer must be a *narrow, structured
  message*, not a shared filesystem. The protocol's job is to make the envelope small enough that
  crossing the boundary costs nothing.
- No network. Everything here stays local-file and git-native.

## Depends on

- STORY-028 — a finding that crosses vaults must carry a stable `id:`, or it arrives unaddressable.
