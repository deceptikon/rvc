---
id: STORY-024
type: story
priority: P1
created: 2026-09-16
domain: workflow_meta
domain_tags: ["plate", "rvc", "protocol", "governance"]
imported-from: "ADLAI STORY-109 §5.3, T-GEN--plate-host"
epic: "[[EPIC-001-RVC-Protocol]]"
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
