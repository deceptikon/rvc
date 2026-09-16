---
type: debate
id: Q-STORY-106-selftest-loop
issue: STORY-106
author: Q
invite: Q
created: 2026-09-13
updated: 2026-09-13
human_gate: false
---

# Debate: where does the decide-queue scan live?

> **Self-test thread** (acceptance-criterion 4 of [[STORY-106]]): one agent occupies both seats
> to verify the arena's file mechanics end-to-end. The question itself is real — STORY-106
> deferred it as "TBD with D" — and internal/engineering, so a unilateral Q verdict is legal
> under the human-gate rule (§5.1). A genuine two-dev thread must look like
> [[Q-NEWVAULT]] × [[big-pickle-NEWVAULT]]; D may re-open this by appending a `## D@…` section
> here **before this file is archived** — after the archive exit, re-open via `20_NEXT`
> referencing this thread, per §4.

## Question block

- **Decision needed:** Does the decide-queue scan (list `40_DECIDE` debates awaiting the running
  agent's verdict) live in the RVC CLI, in `session_bootstrap.sh`, or both?
- **Options:**
  - A) `rvc` subcommand only —
  - B) `session_bootstrap.sh` prompt section only —
  - C) both now (scan logic duplicated).
- **Recommendation:** B (Q) — the scan is a *ritual* step (SYNC: "scan `40_DECIDE` for verdicts
  awaiting you", ROUTING §5), and bootstrap is the ritual driver; it must work on machines where
  `$RVC_BIN` is broken/absent (see the GOTCHAS note on the `$RVC_BIN` fallback), and it needs
  agent identity (`$AGENT`/`STATE.json.agent`) that the CLI deliberately knows nothing about.
- **Default if no answer by 2026-09-20:** B (recommendation stands as default; anti-stale clock
  never fires because the answerer and invitee are the same seat, already answered).

## Q@2026-09-13 (opening position)

A couples vault-agnostic tooling to per-project ritual: `rvc` must stay tree-config-driven and
identity-free (STORY-105 law: the CLI only does `git mv` + tree maps). C duplicates the scan in
two languages before either is proven. B puts the section exactly where the SYNC agent already
reads DECISIONS/GOTCHAS/STATE — one grep loop over `debates/*.md` frontmatter (`status: open`,
`invite:`/`author:` match, `_*` template excluded, `INVITE--to-<me>*.md` file-invites included).
Cost: bash-only. If D later wants `rvc decide` as a convenience alias, it can shell out to the
same scan — extraction is a one-function refactor, not a rewrite.

## Q@2026-09-13 (cross-read of own position — zero open deltas)

Checked the two failure modes A/C claimed to solve: (1) `rvc` present but bootstrap not run →
an agent mid-ritual still misses the queue — irrelevant, the queue *is* a ritual step;
(2) bootstrap on a machine without python/rvc — the bash scan keeps working — pro-B. No deltas.

## VERDICT

- **Outcome:** B — decide-queue scan lives in `session_bootstrap.sh` (all phases + default mode).
- **Rationale:** ritual state belongs to the ritual driver; CLI stays identity-free; works without
  `$RVC_BIN`; C's duplication unjustified before the scan is proven.
- **Affected issues:** [[STORY-106]] (closes the "TBD with D" task), [[STORY-105]] (no coupling
  needed — tree-config stays transition-mapping only).
