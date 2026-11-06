---
id: STORY-039
title: rvc ask — mint an ask as one file, feed the plate's owed lanes
type: story
priority: P1
epic: [[EPIC-001]]
domain: workflow_meta
domain_tags: [ask, plate, feedback, protocol]
imported-from: "ADLAI session 2026-09-29 (forensics on the v5.3→v6.0 arena deletion); relates to STORY-024, STORY-025, STORY-030"
correction: "2026-09-29 — first draft wrongly proposed minting `rvc feedback`; that command already exists as the client→owner INGEST (rvc/feedback.py). Rescoped: ask/answer own the seat→seat direction; feedback owns the client→tool-owner direction."
started: 2026-09-29
---

# STORY-039: rvc ask — mint an ask as one file, feed the plate's owed lanes

**Epic**: [[EPIC-001]] · **Grammar**: STORY-025 · **Cross-vault delivery**: STORY-030

---

## 2026-09-29 — TRIAGED: this is the next thing to build. It is the load-bearing one.

Everything else in the vault is downstream of this, and the reason is now measured rather than
argued. On 2026-09-29, with Avatar v0 shipped, its token configured, and its post-commit hook live
in adlai-vault:

- `avatar/.avatar-state.json` = `{"sent": {}}` — **zero messages ever delivered**.
- `rvc plate --format json` on **both** vaults: `owes_turn: 0`, `owner: 0` — including as the owner.
- The single live data point in the entire system is adlai-vault's hand-typed
  `00_INBOX/DISPATCH-SALWA-CORPUS-DEFECTS.md` (no `id:`, no `type:`, plate renders it `type=—`).

**The wire is built and the sensor is dark.** Delivery is a solved problem (200 lines of stdlib
urllib); *supply* is not, and nothing in the vault mints an ask. This story is the only item that
creates supply. `rvc ask` is also what makes EPIC-004's forum-topic-per-ask design meaningful, what
gives STORY-025 something to derive its grammar from, and what would give STORY-026 a queue rather
than an empty set.

**The decisive argument is this story's own AC5** — "four forever-zero lanes on a vault with live
external dependencies must be impossible to ship." Those four lanes have now sat at `[0]` for 13
days *on top of shipped infrastructure built to serve them*. A regression fixture for that exact
failure is the most valuable line of test code in this repo.

**Scope discipline, restated because it is the whole design:** the tool emits the formal part.
Nobody hand-writes frontmatter, a question block, or a grammar-conformant ask line. That is what
the arena's first version got wrong, and it is why zero asks were minted in two days.

## The forensics (2026-09-29, ADLAI repo, full git history)

The arena graduated here as STORY-025 after ADLAI v6.0 deleted it. Before designing anything
further, the record was checked. Three facts:

1. **The ask was never used once.** `git log --all -p -S'^- \[ \] @' -- 'adlai-vault/40_DECIDE/*'`
   returns **zero** added instances. v5.3 shipped the ask grammar on 09-14; the compile deleted the
   arena on 09-16. Two days of life, zero uses.
2. **The renderer outlived the substrate.** `rvc plate` on ADLAI today renders four lanes —
   *you owe a turn*, *awaiting the owner*, *overdue*, *waiting* — all permanently `[0]` since
   09-16, because nothing that can populate them survived the compile. One unplugged sensor
   (`^status: open` in the decide-queue scan) was removed by shipping another.
3. **The project's real ask is invisible.** The one live external dependency — Salwa, who owes
   corpus fixes — is tracked as `DISPATCH-SALWA-CORPUS-DEFECTS.md`: hand-typed prose in `00_INBOX`,
   rendered by the plate as `type=—`, with no owner field, no default, no date. Meanwhile
   `alias.@salwa=salwa` sits in `.rvc-root`, pointing at nothing.

## Why it failed — the owner's account, and the design consequence

The owner's recollection: after those two days the formalism outpaced its participants. Qwen's
strict grammar made every exchange a compliance exercise; the human stopped being able to follow
what the system demanded of him; other seats (Gemini in particular) lobbied inside the mechanism
instead of through it — and the v6.0 "owner decision" to delete the arena was in practice steered by
a dev seat, not measured by the owner. A comms system whose shutdown requires a lawyer to interpret
is not a comms system; it is a second product competing for the same attention.

The design consequence is not "simpler grammar". It is: **the tool emits the formal part, and
answering costs one command.** Nobody — human or tired agent — should ever hand-write frontmatter,
a question block, or a grammar-conformant ask line. Grammar that must be *learned* will be
*avoided*. Grammar that is *generated* just becomes the file format.

## Relationship to the existing channels

Two directions, two mechanisms — this story owns only the first:

- **Client → tool-owner (exists):** `rvc feedback ⟨file⟩` ingests a client vault's
  `FEEDBACK-<tool>.md` into this vault as a `BUG-<n>` issue, records `origin:`, removes the source
  letter, and the client plate renders what it filed via `plate.source.<name>=`. Design precedents
  to reuse: the tool auto-discovers its own vault next to the CLI, and auto-writes
  `feedback.to=`/`plate.source.*=` memory on first use — the same "the tool emits the formal part"
  philosophy this story applies to asks. **Note:** ADLAI's `.rvc-root` carries neither
  `feedback.to=` nor `plate.source.rvc=` — the ingest has never actually run from there; its four
  inbox letters are all in the pre-ingest state. Wiring that is one `--to` call, not this story.
- **Seat → seat inside a vault (missing — this story):** nothing lets `@deceptikon` owe `@qwen` a
  verdict, or `@salwa` (a human with no vault) owe anyone anything, in a shape the plate can count.
  `owed_by` on a blocked issue is that shape. STORY-030's general `rvc report` remains the
  vault→vault generalization; ask-to-no-vault-seat is the edge neither covers yet.

## Scope

1. **`rvc ask @<handle> "<question>" [--default <text>] [--by <YYYY-MM-DD>]`** mints one file in
   the vault's `tree.block` bucket (`40_DECIDE/`): `owed_by: <canonical handle>` frontmatter plus a
   question block (decision needed / options / recommendation / **default if no answer by**).
   The command, not the caller, guarantees STORY-025 grammar conformity. `--default`/`--by` may be
   omitted only together, and the mint warns loudly when they are (an undated ask is a complaint).
2. **The plate's owed lanes read `owed_by`.** Handle = `plate.owner` → *awaiting the owner*; handle
   = the `--as` caller → *you owe a turn*; past `--by` with no appended answer section → *overdue*.
   Lane semantics land in STORY-024's spec (`specs/PLATE.md`), not in any vault's constitution.
   A vault with no `owed_by` anywhere still renders clean and empty (STORY-025 AC6 holds).
3. **`rvc answer <ID> "<verdict>"`** appends a dated, author-tagged verdict section and transitions
   the file via the existing `issue <ID>` verbs (done, or back to triage when the verdict spawns
   work). The human answerer needs exactly one command and zero frontmatter knowledge.
4. **Seats with no vault.** `rvc ask` targeting a handle with no reachable vault (e.g. `@salwa`)
   still mints the file — the obligation is real — and additionally **prints/emits a deliverable
   message artifact** (numbered ask, default, date) for pasting into whatever channel that human
   actually reads (GitLab issue, chat). The vault tracks the obligation; delivery to a non-vault
   human is explicitly out of scope here — note it as the natural extension of STORY-030's
   `rvc report`, which covers vault→vault only.

## Acceptance criteria

1. `rvc ask` mints a question-block-conformant file with `owed_by:`/`--default`/`--by`; the caller
   writes no frontmatter and no grammar.
2. `rvc plate` shows the minted ask in the correct lane (owner-owed vs `--as`-owed) and in
   *overdue* past `--by` without an answer; a zero-ask vault renders clean.
3. `rvc answer` appends a dated author-tagged section and transitions the file; lane empties.
4. Non-vault seats: ask mints + a copy-pasteable message artifact is produced; the item stays owed
   until answered.
5. **The ADLAI regression becomes a fixture:** mint → plate lane populated → answer → lane empty.
   Four forever-zero lanes on a vault with live external dependencies must be impossible to ship.

## Must not

- Add grammar, scanner law, or any second statement of R1–R10 — STORY-025 owns the grammar; this
  story only *generates* conformant files.
- Add a state field beyond `owed_by` (+ optional `by:`). Folder-as-state stays law; `owed_by` is a
  fact about the file, not a state flip.
- Build a delivery daemon or duplicate STORY-030's cross-vault mechanics, or touch `rvc feedback`'s
  ingest direction — the client→owner channel exists and works as designed.
- Put lane semantics in a vault constitution — STORY-024's spec is their only home.
