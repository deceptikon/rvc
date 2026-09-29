---
id: STORY-026
type: story
priority: P2
created: 2026-09-16
domain: workflow_meta
domain_tags: ["arena", "rvcd", "turn-runner", "automation"]
imported-from: "ADLAI STORY-106, STORY-109 am. 8"
epic: "[[EPIC-001-RVC-Protocol]]"
deferred: 2026-09-29
---

# STORY-026: `rvcd debate` — the turn-runner daemon

**Epic**: [[EPIC-001]] · **Human gate required before implementation**

---

## 2026-09-29 — DEFERRED: orchestration for threads that do not exist

This is the most speculative item in the vault, and the measurement of 2026-09-29 makes it more so.
The runner's job is to drive threads to convergence. **There are no threads.** The arena recorded
zero uses in its two-day life; `rvc plate` shows `owes_turn: 0` and `owner: 0` on *both* vaults,
including as the owner. A turn-runner over an empty queue is a scheduler for nothing — and building
one is precisely how a comms system becomes "a second product competing for the same attention",
the failure the owner's own account blames for the arena's collapse.

**The blockers are also all still live, and two are not this project's to clear:**

1. STORY-025 (grammar the runner reads) — deferred 2026-09-29.
2. `Q-STORY-106-live-turns.md` — D still owes three deltas; the convergence state this is specified
   against is unfinished.
3. ADLAI's `T-GEN--compliance-lane` — unanswered, and it governs whether a runner may *read* corpus
   rows or transcripts. AC5(b) says "do not implement blind". Nobody has answered in 13 days.
4. AC5(a) — may an autonomous loop write into a vault at all — never posed to the owner.

**Re-entry condition, in order:** STORY-039 ships and populates a real owed lane → the grammar is
derived from the tool's actual output (STORY-025) → *then* ask the two human questions above. If the
owed lanes are still empty when this is revisited, the correct answer is to delete this story, not
to build it.

---

ADLAI STORY-106 built the debate substrate by hand and STORY-109 amendment 8 proposed automating it:
`rvcd debate <file> [--max-turns N]`, which launches each owed seat in turn until the thread
converges. It never got built, and ADLAI v6.0 is removing it from its own backlog — the arena is
protocol work, and an autonomous daemon that spawns agent sessions is squarely RVC's subject matter.

## Acceptance criteria

1. Specified **against R9** (turns derive from unchecked `- [ ] @<alias>` boxes) and against the
   table/debate branch that D conceded — not against the pre-R9 header-order design that amendment 8
   was originally written against.
2. `--max-turns` is a hard budget, enforced, with a non-zero exit and a legible reason when a thread
   hits it without converging.
3. Convergence is defined as "zero open deltas", and a runner may not declare convergence — it stops,
   and a human or the seats close the thread.
4. Cost and spend ceiling visible before the first turn, not after.
5. **Human gate, two separate questions:** (a) may an autonomous loop write into a vault at all, and
   (b) may it read vault content that a compliance ruling has fenced. ADLAI's `T-GEN--compliance-lane`
   is still unanswered and it governs whether corpus rows or session transcripts may be shown to
   external models — which is precisely what a runner would be doing. Do not implement (b) blind.

## Blocked by

- **STORY-025** — a runner that cannot tell whose turn it is has no business launching sessions.
- `specs/arena/Q-STORY-106-live-turns.md` — **open: D owes three deltas.** That thread is the
  convergence state this runner must be specified against, and it is not finished. Read it as
  in-progress, not as settled prior art.
- ADLAI's compliance ruling, for criterion 5(b).
