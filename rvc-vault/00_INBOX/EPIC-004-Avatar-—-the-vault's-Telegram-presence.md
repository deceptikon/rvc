---
id: EPIC-004
title: Avatar — the vault's Telegram presence
type: epic
priority: P0
epic: null
domain: workflow_meta
domain_tags: [avatar, telegram, arena, presence, notifications]
created: 2026-09-29
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

## Stories

- **STORY-040 →** (next minted) *avatar v0 crutch* — outbound notify: plate `owes_turn` lanes →
  per-seat DM or group digest; `avatar send` for agents to speak into the group. Stdlib only,
  config file, dedupe state. The crutch that grows.
- *seat linking + long-poll* — `/link` user_id↔handle, `getUpdates` loop, `/ask` mints through
  STORY-039's ask grammar.
- *dev–dev talks* — forum topic per ask; tag-to-turn; verdict buttons append dated sections to
  the ask file; topic archives on verdict.
- *presence* — streaming answers (`sendMessageDraft`); agents join talks as first-class seats.
- *write-back hardening* — verb allowlist, digest of closed topics into the vault, audit.

## Adjacent

- **STORY-039** — the vault-side half: `rvc ask`/`rvc answer` minting + `owed_by` lanes. Avatar's
  outbound reads those lanes; inbound mints through its grammar.
- **STORY-030** — cross-vault finding delivery; `rvc feedback` (shipped) already proves the
  handoff pattern Avatar generalizes to humans.
