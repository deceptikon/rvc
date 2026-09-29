---
id: EPIC-004
title: Avatar — the vault's Telegram presence
type: epic
priority: P0
epic: null
domain: workflow_meta
domain_tags: [avatar, telegram, arena, presence, notifications]
created: 2026-09-29
triage: 2026-09-29
gate: STORY-039
---

# EPIC-004: Avatar — the vault's Telegram presence

> The interface to ping humans, and — in perspective — to initiate and join dev–dev talks.
> The arena reborn in the one place every seat already checks on their phone.

---

## Problem statement

The vault is the record, but it is not a place where conversation lives. The file-arena died of
this (STORY-039 forensics: the ask mechanism was used **zero** times in its two days of life; the
plate's owed lanes have sat at `[0]` since 2026-09-16). The project's critical path runs through a
human (`@salwa`) who will never open a repo. AI devs talk in files nobody reads; humans get
dispatch letters they can't receipt. **There is no live wire between the state and the people.**

## Goal

One bot — **Avatar** — as the vault's presence in Telegram:

- **Outbound (v0):** the vault pings people — owed turns, overdue asks, feedback handoffs.
- **Presence (v1+):** humans and AI devs share a group; tags become turns; dev–dev talks happen
  as threads; verdicts flow back to the vault.
- **Principle:** the vault keeps state (folder-as-state), Telegram holds conversation, and the
  *mapping* is the only bridge. No second state store — that is the bug class that killed v5.3.

## Design core (Bot API knowledge refreshed 2026-09-29)

- **Bot API 10.3** (2026-08-24) — plain HTTPS + JSON. A stdlib client (`urllib`) is enough: no
  framework, no daemon, no webhook infra. This is what makes the crutch path viable.
- **Forum topics** — a supergroup with topics enabled gives *one thread per debate for free*.
  Topic ↔ ask mapping is the arena's structure; pin the ask on open, close the topic on verdict.
- **Live streaming** (`sendMessageDraft`, Bot API 9.5, opened March 2026 for all chat types) —
  a bot can stream a draft answer as it generates, in private chats, groups and topics. This is
  what turns Avatar from a notifier into a *presence*: an agent's long answer renders live, like
  a native Telegram AI bot.
- **Identity** — Telegram users are numeric IDs; `@handles` only surface inside message entities.
  A `/link <handle>` command maps `user_id ↔ vault handle`, reading `.rvc-root` `alias.*` as the
  roster (one source of names; the bot adds no second alias table).
- **Inbound** — group privacy mode off (via @BotFather) lets the bot read plain messages;
  commands-only is the safe v1. Long-polling `getUpdates` needs no TLS, no domain, no public
  endpoint — runs from cron or one process. Webhooks are explicitly out of scope.
- **Deep links** — `t.me/<bot>?start=<ask-id>`: attaching to an ask is one tap. This is how
  `@salwa` gets *into* the system without ever installing anything but Telegram she already has.
- **Inline keyboards + callbacks** — verdict buttons ("take default" / "postpone" / "answer")
  write back through the bot: the only TG→vault writer, appending dated author-tagged sections,
  exactly the one good rule the old arena had.
- **Rate limits** — ~1 msg/s per chat, ~20 msg/min per group: batch pings into one digest
  message per seat per run. A notifier that spams gets muted, and a muted notifier is the
  unplugged-sensor bug again.
- **Formatting** — `parse_mode=HTML` (MarkdownV2 escaping is a known trap).
- **Security** — token at `0600`; group membership is the trust boundary; vault writes limited to
  an allowlist of verbs (mint ask, append verdict); git history stays the audit log.

## Non-goals

No webhook infrastructure. No Mini Apps. No payments. No chat-side state: a deleted group holds
no truth; if it isn't in the vault, it didn't happen.

---

## 2026-09-29 — the diagnosis below is half-falsified; the wire is live and the sensor is dark

This epic was written on 2026-09-29 morning, on the belief that the file-arena died for want of a
**live wire** ("there is no live wire between the state and the people"). By that evening the wire
existed: STORY-040 shipped `avatar notify` and STORY-041 wired a post-commit hook into
`adlai-vault`. The thesis was then testable, and it does not hold as stated.

**What was measured, with the shipped tooling:**

| Claim | Measurement |
|---|---|
| A live wire is now missing | **False.** `avatar hook` is installed in adlai-vault; a commit fires `avatar notify`. |
| Avatar reaches humans | **False.** `avatar/.avatar-state.json` is `{"sent": {}}` — **zero messages have ever been delivered.** |
| The plate feeds Avatar | **Effectively false.** `rvc plate --format json` on *both* vaults: `owes_turn: 0`, `owner: 0` — including as the owner. |
| The arena died for lack of a wire | **Wrong causal story.** The arena died because the *ask* was never minted — 0 uses in its 2-day life (STORY-039 forensics). |

**The one live data point in the whole system** is `adlai-vault/00_INBOX/DISPATCH-SALWA-CORPUS-DEFECTS.md`
— hand-typed prose, no `id:`, no `type:` (the plate renders it `type=—`), no owner field. It is the
single row behind `@salwa owes 1`. Avatar's entire v0 output traces to one human-typed file that no
command produced and no grammar validated. That is the unplugged-sensor bug again, one layer up.

**RVC's own plate is worse — structurally degenerate.** `RVC/.rvc-root` declares no `alias.*` and no
`plate.owner` (adlai-vault declares both). So on this vault `owes_turn` and `owner` can *never* be
non-zero: there is no identity to resolve against. STORY-024 AC3 is the fix and it is unmade.

**What this changes.** The bottleneck is not delivery, and no amount of Telegram surface area
(forum topics, streaming drafts, dev–dev talks) will move it. Telegram is a solved problem here:
stdlib HTTPS, 200 lines, working, installed. The unsolved problem is **supply** — nothing mints
asks, so nothing to deliver. Building v1+ on a dark sensor produces a more sophisticated machine
for transmitting zero.

**Gate: `gate: STORY-039` in this file's frontmatter is binding.** No story below the line
"*seat linking + long-poll*" starts until `rvc ask` exists and has demonstrably produced at least
one real delivery — a human actually pinging a human on Telegram, recorded in `.avatar-state.json`.
That is a one-line check, and it is the difference between this epic being a presence and being
another compliance surface the participants route around.

## Stories

- **STORY-040 → 60_DONE** ✅ *avatar v0 crutch* — outbound notify: plate `owes_turn` lanes →
  per-seat DM; `avatar send`; stdlib only, config file, dedupe state. Shipped, and honest about
  being dark: 0 deliveries.
- **STORY-041 → 60_DONE** ✅ *avatar hook* — idempotent post-commit wiring, live in adlai-vault.
  It faithfully fires on every commit. There is nothing to fire *about*.
- *seat linking + long-poll* — `/link` user_id↔handle, `getUpdates` loop, `/ask` mints through
  STORY-039's ask grammar. **Gated on STORY-039** (see above).
- *dev–dev talks* — forum topic per ask; tag-to-turn; verdict buttons append dated sections to
  the ask file; topic archives on verdict.
- *presence* — streaming answers (`sendMessageDraft`); agents join talks as first-class seats.
- *write-back hardening* — verb allowlist, digest of closed topics into the vault, audit.

## Adjacent

- **STORY-039** — the vault-side half: `rvc ask`/`rvc answer` minting + `owed_by` lanes. Avatar's
  outbound reads those lanes; inbound mints through its grammar.
- **STORY-030** — cross-vault finding delivery; `rvc feedback` (shipped) already proves the
  handoff pattern Avatar generalizes to humans.
