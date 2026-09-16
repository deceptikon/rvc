---
id: ARENA-CORPUS
type: manifest
title: Graduated arena corpus — provenance manifest
created: 2026-09-16
domain: workflow_meta
domain_tags: ["arena", "provenance", "handoff"]
imported-from: ADLAI/adlai-vault
---

# The arena corpus, graduated from ADLAI

**What this is.** ADLAI's Constitution v5.3 grew a multi-seat deliberation machinery — debates,
tables, reviews, seats, turns, a derived plate, an attention scanner, a turn-runner daemon. That
machinery is RVC protocol work, not Saudi-legal-RAG work, and ADLAI's own §7 (domain separation)
says so. ADLAI is compiling it out of its constitution in v6.0; this is where the design comes to
live instead.

**Why a manifest and not edited files.** Every document below is byte-identical to its ADLAI source.
Debate threads are append-only by their own law (§5.1), and several are authored by other agents
(big-pickle, Gemini) — nobody migrating them gets to edit them. So provenance lives here, in one
file, rather than as a header injected into eleven people's text.

**History does not cross the repo line.** `~/X/ADLAI` and `~/X` are separate git repos, so
`git log --follow` dies at the boundary — which is the forensic path ADLAI §1 promises. The commits
below are the compensation: run them in the `~/X/ADLAI` repo and the full thread history is there.

## Provenance

Source vault: `ADLAI/adlai-vault/` · repo `~/X/ADLAI` · last commit touching each file:

- `Q-NEWVAULT.md` ← `40_DECIDE/debates/` @ `c142e3c` (2026-09-14) — Q's position paper; the tree and
  constitution core. Converged 2026-09-13. Cited by ADLAI STORY-104, 105, 106.
- `big-pickle-NEWVAULT.md` ← `40_DECIDE/debates/` @ `c142e3c` — D's counter-paper. The line-level
  `rvc-cli.py` hardcode cites in ADLAI STORY-105 originate here.
- `Q-STORY-106-live-turns.md` ← `40_DECIDE/debates/` @ `c142e3c` — **OPEN: D owes three deltas.**
  This is the convergence state the `rvcd` turn-runner must be specified against. Do not treat as
  settled. See STORY-026.
- `Q-STORY-106-review-loop.md` ← `40_DECIDE/debates/` @ `c142e3c` — reviewer-verdict mechanism;
  source of ADLAI am. 3 and am. 5.
- `Q-STORY-106-selftest-loop.md` ← `90_ARCHIVE/done/` @ `c142e3c` — resolved single-seat mechanics
  test; verdict "the CLI stays identity-free, the ritual driver scans" is in ADLAI's `DECISIONS.md`
  (2026-09-13). **Reopen candidate:** that verdict is why the scanner lives in a shell script, and
  STORY-025 proposes revisiting it now that `rvc plate` exists.
- `INVITE--to-D.md` ← `40_DECIDE/debates/` @ `44cd541` (2026-09-13) — the file-invite that ADLAI am. 3
  ruled must die ("an invitation is a checkbox, never a file") and which stayed alive only because
  the threads above had not cleared. **Deliberate historical artifact, not a live ask.** Do not
  implement it; read it as the reason R4 is phrased the way it is.
- `_TEMPLATE--debate.md` ← `40_DECIDE/debates/` @ `e84dbf6` (2026-09-14) — the debate shape.
- `_TEMPLATE--table.md` ← `40_DECIDE/tables/` @ `e84dbf6` — the table shape, as the *senate*
  understood a table. **Superseded by design:** ADLAI v6.0 redefines a Table as a disposable daily
  workdesk with no seats and no turns. The template survives here only as prior art for the arena
  form; do not reintroduce it into ADLAI.
- `Gemini's reply to STORY-106.md` ← `40_DECIDE/reviews/` @ `e84dbf6` — the outside review that
  generated nine amendments. Owner's ruling on it: "I strongly support PoV stated in this doc."
  Line-accurate against `session_bootstrap.sh` lines 83, 90, 91–95, 98–105.
- `T-GEN--decide-structure-and-plate.md` ← `90_ARCHIVE/done/` @ `c142e3c` — **the source law.** Owner
  signed 2026-09-14; seats Q, D, Gemini. Highest meta-density in the ADLAI vault (77 hits). Its
  `does-not-touch:` field is unusually honest and should be read before anything else here.
- `PROPOSAL--Vault-Constitution-v5.3-and-Tagging-Protocol.md` ← `90_ARCHIVE/superseded/` @ `defaabf`
  (2026-09-13) — §5 of this file is the attention-scanner spec that was archived out of existence in
  the 2026-09-13 inbox sweep and never carried into a story. ADLAI STORY-110 recovered it;
  STORY-025 owns it now. **Read §5 first — the rest is superseded.**

## What is deliberately NOT here

- `T-GEN--compliance-lane` — asks which Saudi regulatory regimes apply (PDPL M/19, NCA ECC, ZATCA
  retention, CMA/SAMA records), data residency, and whether corpus rows or session transcripts may be
  shown to external models at all. It was *filed* in the arena and it is *not* arena business: it is
  an ADLAI product decision. It stays in ADLAI, and ADLAI v6.0 converts it into a `40_DECIDE` issue —
  which is the clearest evidence that "tables became a courtroom" was a real failure and not a
  rhetorical one.
- `T-GEN--culture-home` — asks where the pilot-and-prison-guard essay lives. ADLAI v6.0 answers it by
  executing the split; the question does not travel.
- ADLAI STORY-102, 104, 105, 106, 107, 108, 109, 110 as tickets. A mixed ticket has two owners, so it
  becomes two tickets, one per repo. The graduated halves are STORY-024 … STORY-028 in this vault;
  the ADLAI halves stay in the ADLAI vault, rescoped. Nothing was moved across the repo line that
  would export another domain's scope with it.
- Closed ADLAI tickets 104/105/106/107 as documents. They are the audit trail for why ADLAI's tree
  looks the way it does, and their evidence cites ADLAI product commits. They stay; the ids below
  point at them.

## The receiving tickets

- **STORY-024** — the plate as protocol: lane rules, `.rvc-root` plate config, cross-renderer agreement
- **STORY-025** — ask grammar (R1–R10) as a spec; attention scanner and `--notify` delivery
- **STORY-026** — arena turn mechanics and the `rvcd` turn-runner
- **STORY-027** — transition commits must carry `[skip ci]`
- **STORY-028** — bug: `rvc create` ignores `tree.create`
- **STORY-029** — this vault's own `status:` and priority drift (the same disease, caught earlier)
