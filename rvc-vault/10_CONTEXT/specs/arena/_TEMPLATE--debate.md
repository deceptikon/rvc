---
type: debate
id: Q-STORY-XX-slug
issue: STORY-XX
author: Q
created: YYYY-MM-DD
updated: YYYY-MM-DD
human_gate: false
---

# Debate: <one-line question>

<!--
  TEMPLATE — copy to `<Alias>-<ISSUE-ID>-<slug>.md` (prefix = who opens it; aliases per ROUTING
  §5.2 R2: Q=Qwen, D=big-pickle, G=gemini, K=kimi, C=claude) and delete this comment block.
  Law: ROUTING.md §5.1 (debates) and §5.2 (seats). This file only shows the shape.

  NO `status:` FIELD. Presence in `40_DECIDE/debates/` *is* open; `git mv` to `90_ARCHIVE/done/`
  *is* resolved. Folder = state, without exception (§5.1, STORY-109 am. 2).

  NOT SURE THIS IS A DEBATE? If the answer is the owner's to give, open a **table** instead
  (`tables/_TEMPLATE--table.md`). Debates are where devs converge among themselves;
  `human_gate: true` here means devs still own the question but the outcome needs the owner's
  countersignature (production behavior, spend, external contract). Ask them with a box:
  `- [ ] @deceptikon — <one line>`. Invites are boxes, never files (§5.2 R4).
-->

## Question block

- **Decision needed:** <what exactly is being decided, one sentence>
- **Options:** A) … / B) … / C) …
- **Recommendation:** <option + who recommends + why, in two lines>
- **Default if no answer by YYYY-MM-DD:** <what happens if the arena stays silent — must be a
  real, safe action; the anti-stale clock (§5.1, 7 days) escalates to @deceptikon>

**Asks** — an open box is what makes it that seat's turn; ticking your own box when you append is
receipt, not tidying (§5.2 R4/R9):

- [ ] @D — <what you need from them, one line>

## Q@YYYY-MM-DD

<Position paper. Append-only. Never edit anyone else's section — disagree by appending a new dated
section. Cross-reads go into the *other* dev's file as an appended `## Q@…` / `## D@…` section, the
pattern the NEWVAULT exchange used.>

## D@YYYY-MM-DD

<Answer / cross-read / delta list. Converge to zero open deltas before a verdict.>

## VERDICT

- **Outcome:** <chosen option, one line>
- **Rationale:** <why; what evidence settled it>
- **Affected issues:** [[STORY-XX]] [[EPIC-XX]]
- **Approval (@deceptikon):** required only when `human_gate: true` — a section in the owner's own
  words, not a nod relayed by someone else.

Closing ritual (§5.1): write the VERDICT → append **one** entry to `10_CONTEXT/DECISIONS.md` (the
output log — verdicts live there, process stays here) → `git mv` this file to `90_ARCHIVE/done/`.
There is no status field to flip. A resolved debate never lingers in `debates/`.

---

## Completed samples (read-only, do not copy-edit)

[[Q-NEWVAULT]] × [[big-pickle-NEWVAULT]] — the two-dev thread this template encodes: two position
papers, cross-reads appended into each other's files, converged with zero open deltas; its verdict is
the constitution itself (ROUTING v5.x). For the four-seat variant (owner + three AI devs, mixed
verdicts and concessions), see [[T-GEN--decide-structure-and-plate]].
