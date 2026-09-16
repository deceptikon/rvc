---
id: STORY-025
type: story
priority: P1
created: 2026-09-16
domain: workflow_meta
domain_tags: ["arena", "scanner", "notifications", "protocol"]
imported-from: "ADLAI STORY-110 task 1, v5.3 proposal §5, ROUTING §5.2 R1–R10"
epic: "[[EPIC-001-RVC-Protocol]]"
---

# STORY-025: Ask grammar and the attention scanner

**Epic**: [[EPIC-001]] · **Prior art**: `specs/arena/README.md`

---

Rules R1–R10 (one question per file, canonical aliases, seat authority, invitations-as-checkboxes,
disposition-not-deletion, duty-binds-the-author, turns-from-open-asks) were written into ADLAI's
constitution. They are protocol: every multi-seat vault needs them and ADLAI v6.0 is deleting them
from its own law. If nobody transcribes them here, they are lost the moment the compile lands — which
is the exact failure that already happened once to this same document set.

**The precedent that must not repeat.** On 2026-09-13 an inbox sweep sent the v5.3 proposal's §5
attention-scanner design to `90_ARCHIVE/superseded/` without it being carried into any story. ADLAI
STORY-110 spent a session recovering it. Archiving a document as superseded is not the same as its
content having a home, and a keyword match is not a diff.

## Acceptance criteria

1. R1–R10 transcribed into `specs/ARENA.md` as protocol law, with the ask grammar stated strictly:
   the head is one or more handles, separated from a single-line note by the first whitespace-flanked
   `- `, ` — ` or ` : `. Text inside fenced code blocks is never an ask. `_`-prefixed files are
   shapes, not surfaces.
2. **Turns come from open asks, not from the last header** (R9). With N seats, any header-derived rule
   alerts everyone except the last speaker, forever. State this as a theorem with the two-seat case
   that produced it.
3. The scanner's duties split cleanly: which checks belong to the CLI, which to a ritual driver, which
   to a notification daemon. `rvcd` and `--notify` are delivery; R1–R10 is the grammar they read.
4. Revisit the 2026-09-13 verdict "the CLI stays identity-free, the ritual driver scans" (ADLAI
   `DECISIONS.md`, and `specs/arena/Q-STORY-106-selftest-loop.md`). That ruling predates `rvc plate`,
   which today recomputes exactly the ask analysis the shell script performs — and performs it badly:
   ADLAI's `session_bootstrap.sh:90` still filters debates on `^status: *open`, a field ADLAI
   forbidden three days ago, so **its decide-queue scan has matched nothing since the day it shipped.**
   Decide: does identity resolution belong in the CLI after all?
5. Team constants (handles, the owner's handle, the priority vocabulary) stay in `.rvc-root` config.
   The CLI reads config and knows nothing about any particular team. Carried verbatim from ADLAI
   STORY-110's `Must not`, because it is the constraint that makes this portable.
6. A vault that opts out of the arena entirely — as ADLAI now does — must be able to omit the config
   and get a clean, empty, non-erroring result. Silence is a valid plate.

## Definition of done

- ARENA.md holds R1–R10 with the ask grammar as a strict, machine-checkable definition
- Verdict recorded on criterion 4 either way, with reasoning
- The scanner/notify spec has a home, and nothing in it names ADLAI

## Depends on

- Nothing. Blocks STORY-024 (lanes 1–2) and STORY-026 (a runner that cannot tell whose turn it is has
  no business launching sessions).
