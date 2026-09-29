---
type: meta
tags: [workflow]
domain: workflow_meta
domain_tags: ["rvc", "protocol"]
revised: 2026-09-29
---

# RVC Evolution Roadmap

The goal: a **local-first protocol** where a vault is the state, a CLI is the only way to change
it, and no human ever has to open a repo to be part of a dev loop.

## Where the project actually is (2026-09-29)

Shipped and load-bearing: folder-as-state lifecycle, `rvc init` (STORY-037/038), semantic context
retrieval (STORY-033), the plate as the single renderer, `rvc feedback` cross-vault ingest
(STORY-036/039-PoC), stdlib test suite (114 green), Avatar v0 outbound (STORY-040/041).

**The measured problem, stated honestly:** the platform's attention sensor emits nothing.
`rvc plate` on both vaults reports `owes_turn: 0`, `owner: 0`. Avatar has delivered **zero**
messages — `avatar/.avatar-state.json` is `{"sent": {}}`. The one live owed row in the system is a
hand-typed prose file in adlai-vault's inbox. The wire is built; the supply is not.

## Milestones

- [x] **Core Lifecycle Automation** (STORY-001) — status shifting logic
- [x] **RVC Scaffolder** (STORY-002 → shipped as STORY-037/038) — `rvc init`, newvault layout
- [x] **Real MCP Server Integration** (STORY-003) — agent tool discovery
- [x] **Context Engine** (STORY-033/034) — semantic retrieval, hardening, `--as` identity lanes
- [x] **Cross-vault feedback** (STORY-036) — `rvc feedback`, external BUG lane
- [x] **Git-Sync Automation** (STORY-007) — locking and sync rules
- [x] **Avatar v0** (STORY-040/041, [[EPIC-004]]) — outbound notify + post-commit crutch
- [ ] **The plate renders a non-empty owed lane** (STORY-039 + STORY-024) — ⬅ **the whole game now**
- [ ] **No `shell=True` in the git path** (STORY-013)
- [~] **Obsidian Templater / Dashboards / Graph DB** (STORY-004/005/006) — **superseded**; the graph
      backend is EPIC-004's explicit anti-goal ("no second state store")
- [~] **Conductor v0.2** (EPIC-002/003) — superseded into the conductor repo

## Current focus (Q3 2026)

1. **`rvc ask` / `rvc answer`** (STORY-039) — mint an ask in one command; the plate's owed lanes
   read `owed_by`. The only item that creates supply for everything above. Ships with a regression
   fixture that makes forever-zero lanes unshippable (AC5).
2. **Make the plate honest on RVC's own vault** (STORY-024 AC3/AC5) — `.rvc-root` gains
   `alias.*` + `plate.owner`; without it the two identity lanes are structurally unreachable, and
   every measurement taken from this vault reads a dead sensor.
3. **Kill `shell=True`** (STORY-013) — 27 call sites, a live bug class (BUG-03), and a ticket that
   was filed as done without the work.
4. **Avatar v1** — *gated on (1).* The gate is real, not caution: one verified human-to-human ping
   recorded in `.avatar-state.json` before forum topics or streaming drafts are built.
