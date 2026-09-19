# DECISIONS — Architectural Decisions (rvc-vault)

Format: `## <date> — <agent> — <title>` + 2–4 lines of rationale. Never delete the *why* of a
live decision; compress superseded ones to one line pointing at the resolving commit/story.

## 2026-09-19 — opencode — transitions read calmly, the lock never lingers (STORY-035)
- **Transitions never spray raw git errors on untracked sources.** `sync_before` skips
  `git pull --rebase` when the tree is dirty (a rebase pull would abort with
  `cannot pull with rebase` anyway — skipping is calmer and loses nothing); `cmd_issue_action`
  probes trackedness and takes a plain move with `[RVC] <name> is untracked — plain move` instead
  of cascading `git mv failed (fatal: not under version control)` + `could not stage` warnings.
  `sync_after` only `git rm --cached`s a moved-away path when it exists in the commit index, so a
  never-committed deposit contributes nothing to the index bookkeeping. Rationale: the transition
  landed correctly before — the fix is honesty of output, not a behavior change.
- **`create --body` never renders two H1s.** The CLI owns the canonical
  `# <ID>: <title>` heading; one redundant leading H1 in the body is stripped. Rationale: the ID
  must stay in the heading, so the body's copy goes.
- **The create lock cleans up after itself — and knows a stale one from a live one.**
  `.rvc-create.lock` is unlinked on exit (only while the path still names the inode we flocked, so
  a replacement file is never deleted); a leftover `pid=<dead>` marker is reclaimed with an
  explicit notice, and the timeout message names the holder pid. Rationale: the flock was always
  the authoritative lock — the stale pid file was pure confusion on top of it.

## 2026-09-17 — opencode — transitions never lie, never sweep, and the plate can rewrite itself (STORY-034)
- **A transition must resolve its handle before it prints anything.** `rvc issue <ID> <verb>` now
  exits non-zero with `no issue matches <ID>` before `sync_before` runs — a false green (printed a
  move that never happened) is worse than an error, because the operator trusts the bucket.
- **RVC commits only what RVC staged.** `sync_after` commits from a throwaway index seeded with
  `git read-tree HEAD` (GIT_INDEX_FILE), staging only the moved/created paths (add for survivors,
  `git rm --cached` for a `git mv`'d-away path), then re-stages survivors in the real index. A bare
  `git commit` can never sweep an operator's pre-staged work again; argv subprocess calls also kill
  the shell-quoting bug class for messages with apostrophes.
- **`rvc plate --write` persists the rendering.** PLATE.md is "a rendering, not a record" per the
  constitution, so text output is refactored to one string; `--write` writes that exact string to
  `tree.roadmap/PLATE.md` (10_CONTEXT). Without `--write`, stdout-only behavior is untouched; JSON
  is a data payload and is never persisted.
- **Triage owns the type gate.** `rvc issue <ID> triage` reads frontmatter `type:` and refuses
  non-issue types (`proposal`, `feedback`, …) with a stderr warning — those documents have no
  bucket mapping and were rotting in 40_DECIDE. Other verbs (block, supersede, done, …) still route
  any file; the gate is triage-only.

- Dogfooding note: this vault moved to the **newvault** tree on 2026‑09‑13 (`rvc project init
  --tree newvault`), legacy content migrated by `git mv`, root `README.md` regenerated from
  `README_TEMPLATE`. Deep specs: `10_CONTEXT/specs/DECISION-Domain-Structuring.md` (domain
  structuring rationale) and `10_CONTEXT/specs/PROTOCOL.md`.

## 2026-09-16 — opencode — `rvc context` is semantic BM25, identity-keyed, budgeted (STORY-033)
- **Stdlib BM25 over chunks, not wikilinks.** The legacy resolver only read explicit links and dumped
  referenced files whole (60–90K chars). `rvc context` now extracts the target's weighted term
  footprint (title/id 3x, tags 2.5x, headings 2x, body 1x; kebab ids split; numerals zero-stripped so
  `STORY-33` ≡ `STORY-033`) and ranks every vault doc with BM25 (k1=1.5, **b=1.0**). b=1.0 is full
  length normalization: a long debate transcript must not outrank a short reference by accumulating
  weak matches (hand-labeled benchmark recall@5: 77% at b=0.75 vs 92% at b=1.0). A doc's score is its
  best section, so soft refs are excerpt-grade without an LLM. No pip, no model, no network.
- **Identity is the Document ID; the path is a pointer.** `.rvc-context-cache.json` is keyed by
  `id: STORY-033` / `ROUTING`, never by folder. `rvc issue <ID> <action>` repaths on `git mv`
  (mtime+size match, zero re-tokenization); `rvc create` folds the new file in when a cache exists;
  `rvc rescan` force-rebuilds. Cache is vault-local, git-ignored, atomically written; missing or
  corrupt caches cold-start transparently. Cold build ~290 ms / 60 docs; warm update ~18 ms.
- **Ranking policy (owner-approved).** Archive buckets (`tree.evict`/`tree.supersede`) are indexed —
  hard links may point there — but never offered as soft suggestions. Docs under the vault's
  knowledge root (`tree.roadmap`, e.g. `10_CONTEXT`) carry a prior (root ×1.5, nested ×1.2): `rvc
  context` exists to surface the constitution, DECISIONS, GOTCHAS and specs, not debate transcripts.
  Measured recall@5: 69% without the prior, 92% (12/13) with it, enforced by
  `tests/test_context_benchmark.py`. The remaining miss (`STORY-028` → `STORY-029`) is a semantic
  label with no lexical bridge — the documented ceiling of the stdlib tier.
- **Budget.** `--budget` (default 40000 chars). Degradation order is target > hard refs > soft refs;
  each block goes full → summary (frontmatter+title+headings+first 500 chars) → truncated notice →
  omitted notice → gone, and dropped soft refs leave a section-level omission notice. `--mode
  summary` prints frontmatter+goal+ACs; `--no-semantic` keeps the legacy wikilink-only behavior.

## 2026-09-16 — opencode — the vault is RVC's; Conductor's work moved out (20 issues archived)
- **Three projects had been filed as one vault.** EPIC-001 is RVC tooling; EPIC-002/003 are the
  **Conductor** pipeline (`conductor/pipeline.py`) — and Conductor already owns them, both in
  `conductor/10_Issues/` and in `conductor/conductor/stories/` (story-015…023 are byte-for-byte the
  same stories that sat here). The RVC vault now holds only RVC's subject matter.
- **Routing:** 4 → `90_ARCHIVE/done` (STORY-002 scaffolder already shipped as `rvc init`; STORY-008
  shell=True, STORY-009 PlanReviser, STORY-010 tests landed in Conductor). 16 → `90_ARCHIVE/superseded`
  (EPIC-002/003 + their non-landed children 011–012, 015–023; plus the dropped vision 004–006).
- **Why not delete:** the Conductor epic is live work, just not *this* vault's. A superseded copy
  keeps the provenance and the argument; deleting it would make a future reader re-derive why it
  left. `20_NEXT` is now 8 issues that all describe one project: *make `rvc` a better vault tool.*

## 2026-09-16 — opencode — `create` is lock-safe: flock serializes ID minting (STORY-013 AC4/AC5)
- **The race:** `_next_id()` is a high-water-mark scan followed by `max+1`, and file creation
  happened outside any lock. Two concurrent `rvc create` calls both scanned, both minted
  `STORY-XXX+1`, and one silently overwrote the other's file — a lost issue, no error.
- **Choice: `fcntl.flock` on `.rvc-create.lock`, not a `.rvc-root` flag.** A boolean "locked" line
  in `.rvc-root` is not atomic across processes (check-then-set races, and a crash leaves it stuck
  set forever). `flock` is kernel-arbitrated and auto-released when the fd closes, so a killed
  process cannot wedge the vault — no stale-lock cleanup. The lock covers mint+write only; git's
  own index lock handles the subsequent commit. A 30s timeout fails loudly on a wedged peer
  instead of blocking forever. Lock file is vault-root-local and git-ignored.
- **Test pins the contract:** `tests/test_create_concurrency.py` runs 8 real OS processes; with the
  lock they mint exactly `STORY-01..08`. Without it the same harness produces duplicates/clobbers.

## 2026-09-16 — qwen — local zero-dependency test suite; create/plate fixes (STORY-028, STORY-031)
- **Test suite as an independent tool:** RVC now ships `tests/` with a stdlib-only runner
  (`python3 tests/run_tests.py`, no pytest/network/conductor). Scratch vaults live under
  `/tmp/opencode` with **no `.git`**, so `sync_after`/`find_git_root` no-op — a failing test can
  never commit.
- **`_next_id` padding derives from the high-water mark width** (STORY-028): a 3-digit vault
  (`STORY-010`) keeps minting 3-digit ids (`STORY-011`) instead of flipping to `STORY-11`; a fresh
  vault still starts at `STORY-01`. Mixed-width vaults keep the widest form.
- **`40_DECIDE` root stories are first-class waiting items** (STORY-031): the plate's waiting lane
  now includes *issues* blocked on a ruling (previously only non-issue proposals rendered), matching
  ADLAI's DQL "Awaiting a ruling". They join `waiting_paths`, so a blocked decision is waiting on the
  owner's clock — never mislabeled overdue.

## 2026-09-16 — qwen — constitution guard: `rvc doctor` + mint refusal (STORY-029)
- **The guard is the fix, not the sweep:** stripping `status:` from 26 files fixes today's drift;
  `rvc doctor` (audit + `--fix`), the create-time refusal, and the rescan normalizer stop it from
  regrowing. Two independent vaults growing identical rot proved the failure was in tooling, not
  team discipline — so the tool owns the law. ADLAI's `LEGACY_PRIORITY_TO_P` translation proves the
  tool can detect; it just only did so at creation, never on audit.
- **`doctor` is scoped to trees that declare a `block` bucket:** folder-is-state law only exists on
  newvault trees. Legacy trees (no `block`) keep their status/priority conventions untouched — the
  guard refuses nothing there. Archive buckets (`90_ARCHIVE/*`) keep what they were filed with.
- **Priority folding is tier-preserving:** strays fold to their declared base tier (`High`→`P1`,
  `P0.0.0`→`P0`) rather than being flattened to a default — the author's intent survives, the
  queue stays P0-P3 sortable.

## 2026-09-13 — big-pickle — push is opt-in; `create` honors the create bucket
- **Opt-in push:** `cmd_issue_action` was silently running `git push` after every transition and
  synced `origin/main` during a doc-only commit (unintended). Now `_push_enabled()` gates it —
  env `RVC_PUSH=1` or `push=true` line in `.rvc-root`. `sync_after` always commits; push never
  happens unless the operator explicitly enables it, and a "Skipping push" notice is printed.
  Rationale: transitions are local bookkeeping; pushing is a deployment act.
- **`create` lands in `tree.create`:** `cmd_create_issue` defaulted to `tree["triage"]`, so
  newvault vaults put new issues in `20_NEXT` instead of `00_INBOX` (tree law violation). Now
  `tree.get("create") or tree["triage"]`, with a dynamic hint (`triage` when the create bucket
  differs from triage, else `start`).
## 2026-09-19 — big-pickle — external feedback = BUG-<n>, client alias is rendering (STORY-039 PoC)
- **No parallel type.** Client feedback (`rvc feedback @<file>`) is ingested as a regular
  `BUG-<n>` issue in the RVC vault — `bug` already gates into triage and plate with zero
  registration. The letter's content becomes the body; `origin: <client>` frontmatter records
  the submitter; the canonical `# <ID>: <title>` heading replaces the letter's own H1.
- **One-letter alias is display-only.** The client's plate renders RVC bugs as `F-<n>`
  (`plate.alias.<name>=F`) purely to signal provenance — "this is *our* feedback to rvc, not
  our own bug". Ids on the RVC side stay `BUG-<n>`: "rendering, not a record".
- **Derived lane, not an export.** `plate.source.<name>=<vault>` on the client's `.rvc-root`
  points the plate at the external vault's tree; the lane shows IDs and counts only — no
  content crosses the boundary. Lifecycle stays folder-owned on the RVC side.
- **The letter travels.** Source file is removed after ingest (`git rm` + commit when tracked,
  plain delete otherwise), with `--no-remove` as an escape hatch.
- **Setup is automatic (amended during review).** A client never hand-edits `.rvc-root`.
  Target resolution: `--to` > `feedback.to=` (the line the tool itself wrote) >
  `RVC_FEEDBACK_TO` > auto-discovery of the `rvc-vault/` sibling of the installed CLI
  (`realpath(argv[0])` — the launcher lives in RVC's own repo). First use self-writes the
  client's `feedback.to=` / `plate.source.<name>=` / `plate.alias.<name>=` idempotently
  (user values win; a vault never configures itself). Validated in a throwaway TestProject
  sandbox before any live-vault rollout.
