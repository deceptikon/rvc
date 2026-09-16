---
type: table
id: T-STORY-XX-slug
issue: STORY-XX
author: Q
decides: @deceptikon
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# Table: <one-line question the owner must answer>

<!--
  TEMPLATE — copy to `T-<ISSUE-ID>--<slug>.md` (or `T-GEN--<slug>.md` for a question about the law
  itself; child of another table = `T-<parent-ID>--<sub-slug>.md`, §5.2 R1) and delete this block.
  Law: ROUTING.md §5.2. Shape only.

  A TABLE IS NOT A DEBATE. The answer is the owner's to give. Devs may converge completely and the
  table still correctly waits here — that is the human gate working, not drift (R3). So:

  - **Your sections are evidence.** Do not write a `## VERDICT` on a table. Write the question, the
    options, the recommendation, and the cost of each — then stop.
  - **Only an `## @deceptikon@<date>` section is a verdict.** Their words, their section, their hand
    on the approval box. A relayed "approved" from another seat is a note, not a signature.
  - **Asks are checkboxes and they are non-owning** (R4): a visitor appends one dated section, ticks
    their own box, and owes nothing further — no cleanup, no eviction, no filing.
  - **Disposition is yours, not the next bootstrapper's** (R5/R6): before your session ends, take one
    of three doors — verdict (owner signed) / file (deltas become issues) / park (to `50_DEFERRED/`).
    Park is legal. The rule demands a disposition, never a decision.
-->

## Question block

- **Decision needed:** <one sentence, phrased so a "yes", a "no", or an option letter answers it>
- **Options:** A) … / B) … / C) …
- **Recommendation:** <option, who recommends it, why, in two lines>
- **Cost of waiting:** <what stalls while this is open — and what it costs if it is never decided>
- **Default if no answer by YYYY-MM-DD:** <a real, safe action; 7 days of silence escalates (§5.1 R7)>

**Asks** — open box = that seat owes a turn (R9):

- [ ] @deceptikon — <the decision, one line>
- [ ] @G — <what you want from them, one line>

## Q@YYYY-MM-DD

<Evidence: what was checked, what the tree says, what breaks either way. Cite paths and commands, not
memory. Append-only; never edit another seat's text.>

## @deceptikon@YYYY-MM-DD

<The verdict, in the owner's own words. Anything else in this file is input until this exists.>

---

Closing ritual (§5.2 R5, verdict door): owner section lands → append **one** entry to
`10_CONTEXT/DECISIONS.md` → `git mv` to `90_ARCHIVE/done/`. If the answer spawns work instead, the
**file** door applies: open the issues, then exit the same way. If priorities simply moved, take the
**park** door to `50_DEFERRED/` with a date, and let the plate's *waiting* lane show it (§5.3).
