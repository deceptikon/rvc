---
id: STORY-040
title: Avatar v0 — outbound ping: plate owed turns → Telegram digest
type: story
priority: P1
epic: "[[EPIC-004]]"
domain: workflow_meta
domain_tags: [avatar, telegram, notify, mvp]
created: 2026-09-29
---

# STORY-040: Avatar v0 — outbound ping: plate owed turns → Telegram digest

**Epic**: [[EPIC-004]] · **Scope discipline**: MVP only. Тише едешь — дальше будешь.

---

## What v0 is

One script, two verbs, zero dependencies beyond Python stdlib:

1. **`avatar notify --vault <path>`** — for each seat in config, read `rvc plate --as <handle>
   --format json`, collect the *you owe a turn* lane, and send one digest message per seat:
   DM if the seat has a `chat_id`, group `@mention` otherwise. Dedupe via a state file so a cron
   run doesn't re-ping the same ask every hour.
2. **`avatar send "<text>"`** — post a message into the group. This is how any AI dev speaks into
   the arena from a session (the human-side half arrives in later stories).

No token configured → print the message instead of sending (crutch dry-run; the chain stays
testable end-to-end before the owner's BotFather token lands).

## Acceptance criteria

1. `avatar notify` delivers **one real ping** when a seat owes a turn — the live test is the
   ADLAI plate, where `@salwa` currently owes one on `DISPATCH-SALWA-CORPUS-DEFECTS.md`.
   **⏳ pending owner's BotFather token** — everything else verified dry (2026-09-29):
   dry-run detects the real owed turn (`@salwa owes 1`), send-verb prints the DM.
2. ✅ Second run with no new asks sends nothing (dedupe via `.avatar-state.json` — verified).
3. ✅ `avatar send` posts a message (dry path verified; live pending token).
4. ✅ Without a token, both verbs run as visible dry-runs and exit 0.
5. ✅ Config is one JSON file (`token`, `seats: {handle: {chat_id?}}`); token override via
   `AVATAR_TG_TOKEN`; state file holds only dedupe keys; both gitignored.

## Implementation

- `avatar/avatar.py` — stdlib only (`urllib`, `json`, `subprocess`); reads the plate through the
  `rvc plate --as <handle> --format json` CLI surface, never rvc internals.
- Personal channel per owner's call (2026-09-29): no group yet — the bot DMs seats; `avatar
  updates` bootstraps chat_ids from whoever /starts the bot. Group/dev–dev talks = later stories.
- A seat without a chat_id is reported (`@salwa owes 1 but has no chat_id`) — never silently
  dropped; an unplugged sensor is the bug class, not a state.

## Explicitly NOT in this story

- Seat linking, `/link`, long-poll `getUpdates` (v1)
- Forum topics, ask↔topic mapping, verdict buttons (v2)
- Streaming / `sendMessageDraft` (presence stories)
- Any ADLAI-side wiring — that is a separate thin story *after* v0 runs live once. The crutch is
  how we attach the tool to ADLAI later; building it now would be running before walking.

## Depends on

- Owner: bot token from @BotFather + group chat id (pending — token promised).
- The plate's ask lanes (already live; ask boxes scan in every bucket — verified on ADLAI
  2026-09-29, `@salwa` renders `[1]` in her lane).
