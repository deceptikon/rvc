---
id: STORY-024
type: story
priority: P1
created: 2026-09-16
domain: workflow_meta
domain_tags: [plate, rvc, protocol, governance]
imported-from: "ADLAI STORY-109 §5.3, T-GEN--plate-host"
epic: "[[EPIC-001-RVC-Protocol[rvc]]]"
---

# STORY-024: The plate is protocol, not a vault's local opinion

**Epic**: [[EPIC-001]] · **Prior art**: `specs/arena/README.md`

---

`rvc plate` already renders seven lanes (`rvc-cli.py:1036`), and ADLAI's `PLATE.md` renders the same
lanes as Dataview. But the *lane rules* exist only inside ADLAI's constitution §5.3, and this vault's
`.rvc-root` declares no `alias.*` or `plate.owner` at all — so `rvc plate` here runs degenerate.

A second vault will want a different lane set. What must not happen is each vault re-inventing lane
semantics in its own constitution, which is how ADLAI ended up maintaining seven lanes in two
languages that nothing proves agree.

## 2026-09-29 — AC1 and AC2 are already landed; AC3 is the one that bites

This sat in the ready queue reading as greenfield. It is two-thirds done and the remaining third
is the actual defect:

- **AC1 ✅** — `10_CONTEXT/PLATE.md` exists and states the lanes.
- **AC2 ✅** — waiting≠late is implemented, not just written: `rvc/plate.py:273-277` routes
  `40_DECIDE` and `50_DEFERRED` items into `waiting` and into `waiting_paths`, which exempts them
  from the overdue sweep (`plate.py:279-287`). The exemption is structural — a blocked decision
  cannot be mislabelled late.
- **AC3 ❌ — and it is the live bug.** `RVC/.rvc-root` still declares no `alias.*` and no
  `plate.owner`. Verified: `rvc plate --as @deceptikon --format json` → `owes_turn: []`, `owner: []`.
  Not "empty because nothing is owed" — **structurally unreachable**, because there is no identity
  to resolve against. The two lanes this protocol exists to make trustworthy are the two that
  cannot render on RVC's own vault. ADLAI's `.rvc-root` has the block; RVC's does not.
- **AC4 ✅** — identity stays a caller filter (`--as`), never vault state.
- **AC5 ❌** — no cross-renderer agreement fixture in `tests/`.
- **AC6 ❌** — unrecorded.

**Why this is now a blocker for the epic, not a documentation chore.** EPIC-004's Avatar reads
exactly these lanes, and STORY-039's AC2 says lane semantics land in *this* story's spec. Closing
AC3 makes the plate honest on the vault that dogfoods the tool; without it, any measurement drawn
from RVC's own plate (including the one in EPIC-004) is reading a dead sensor.

**Sequencing:** land AC3 + AC5 with STORY-039 in one session — same files (`.rvc-root`, `plate.py`,
`specs/PLATE.md`), and 039's AC5 fixture ("four forever-zero lanes must be impossible to ship") is
precisely the regression AC5 asks for.

## Acceptance criteria

1. The lane definitions move out of any single vault's constitution and into a protocol spec
   (`specs/PLATE.md`), stating for each lane: what it selects, what makes an item appear, what makes
   it disappear.
2. **Waiting and late are different lanes, always.** An age-sorted list that renders "the owner is
   handling this on his own clock" as negligence gets the whole list ignored. This is the single most
   load-bearing property of the design and it must be normative text, not a comment.
3. `rvc-vault/.rvc-root` gains an `alias.*` + `plate.owner` block, and `rvc plate` on this vault
   renders the same seven lanes it renders on ADLAI.
4. Reader identity stays a caller-supplied filter (`--as`), never vault state.
5. A cross-renderer agreement fixture exists: build a fixture vault, assert the filesystem lane
   membership matches what the documented DQL selects. **This closes the question ADLAI left open**
   — "is unverified DQL in production acceptable?" — with a test rather than an opinion.
6. Where a vault holds a second board surface (ADLAI's `DASHBOARD.canvas`), the protocol says
   explicitly that a rendering which cannot be rebuilt from the tree is a bug, not a feature. ADLAI
   retires its canvas in v6.0; record the reasoning here so the next vault doesn't rebuild one.

## Definition of done

- Lane semantics documented once, in this vault, and quoted rather than restated by consuming vaults
- `rvc plate` works on rvc-vault with real config
- Agreement fixture in RVC's own test suite, and it fails if the two renderers diverge

## Depends on

- STORY-025 (lanes 1–2 select open asks; the ask grammar must be specified first)
