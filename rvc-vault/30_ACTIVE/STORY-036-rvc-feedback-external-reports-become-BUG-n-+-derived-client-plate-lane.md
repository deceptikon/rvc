---
id: STORY-036
title: rvc feedback: external reports become BUG-<n> + derived client plate lane
type: story
priority: P2
started: 2026-09-19
---

# STORY-036: rvc feedback: external reports become BUG-<n> + derived client plate lane

External friction reports (ADLAI, conductor, dash, ...) currently travel as hand-moved
`FEEDBACK-<tool>.md` letters (see 90_ARCHIVE/superseded/FEEDBACK-rvc.md). This story turns
that dance into one command with a real, trackable type of work — no parallel machinery.

# Design (decided — see DECISIONS.md 2026-09-19)

- **BUG-<n>, not F-<n>:** client feedback is ingested as a regular `bug` issue in the RVC
  vault — `bug` already gates into triage and plate with zero registration.
  `origin: <client>` frontmatter records the submitter.
- **F-alias is rendering, not a record:** the client's plate draws `plate.alias.<name>=F`
  to show `BUG-14` as `F-14` — provenance display only; the RVC record stays `BUG-14`.
- **Derived lane, not an export:** `plate.source.<name>=<vault>` on the client's
  `.rvc-root`; the lane carries IDs and counts only, nothing else crosses the boundary.
- **The letter travels:** the source is removed after ingest (`git rm` + commit when
  tracked, plain delete otherwise, `--no-remove` to keep).

# Acceptance criteria (test-backed)

- AC1 — `rvc feedback @<file>` ingests into the target vault as `BUG-<n>`
  (`type: bug`, `origin:` frontmatter), strips the letter's redundant leading H1,
  removes the source, prints the dashboard line — `test_feedback_ingest.py`.
- AC2 — sequential minting honors padding (BUG-07 on disk → BUG-08).
- AC3 — `feedback.to=` in the client's `.rvc-root` replaces `--to`.
- AC4 — client plate gains an `EXTERNAL FEEDBACK` lane, F-alias in text & JSON —
  `test_plate_external.py`.
- AC5 — without `plate.source.*` the plate is unchanged (no behavioural change).
- AC6 — client-side protocol snippet published: `10_CONTEXT/specs/FEEDBACK-PROTOCOL.md`.

# Dogfood trail

- PoC committed `fc9d5e5` (`rvc feedback` + plate external lane + 7 tests).
- Live demo: ingest BUG-01 from a scratch client → plate shows `F-01` →
  triage/done on RVC → client plate flips to `done: 1 of 1`.
- Demo dogfooded STORY-035 too — the new bug's first transition printed the
  "untracked — plain move" note.

# Review amendment (2026-09-19)

Review caught a UX gap: a client must not hand-edit `.rvc-root`. Setup is now automatic —
`rvc feedback` resolves the target from `--to` > the client's own (auto-written)
`feedback.to=` > env > auto-discovery of the `rvc-vault/` sibling of the installed CLI, and
self-writes the client's `feedback.to=` / `plate.source.rvc=` / `plate.alias.rvc=F` lines on
first use (idempotent, user values win, a vault never configures itself). Four new tests
(96 passed). Still to be validated in a throwaway TestProject sandbox before any live-vault
rollout.

# DoD

- Suite green (92 passed, 0 failed).
- Story closes via normal lifecycle verbs.
- Client instruction published and referenced from the client's side.
