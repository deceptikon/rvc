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
- **Init lays the vault in a named subdir (`0-vault`), marker/gitignore at the project root (STORY-037).**
  `rvc init` asks for the vault name (suggesting `0-vault`; `--vault-name` for scripts, silent
  default when not a tty). The vault holds only the tree buckets + ROUTING; `.rvc-root`
  (`vault=<name>` + `tree.*`) and `.gitignore` live outside it. Resolution: `find_vault_root`
  descends via `vault=` only when that child exists AND has no marker of its own (self-referential
  inner markers like `vault=rvc-vault` and old flat markers stay put); `find_marker_dir(vault_path)`
  returns the single authoritative marker (the vault's own, else the project root) used by tree
  config, plate lanes, `push=` and the automatic feedback config. No legacy/newvault dualism — one
  command, always the same structure; re-runs append missing files/lines and reuse the existing
  name, never overwriting.
- **RVC itself adopts the new layout via marker relocation — data never moves (STORY-038).**
  A stray `rvc init` at the RVC repo root minted a second `0-vault` and repointed the
  AGENTS/CLAUDE/GEMINI/QWEN links at it. Instead of migrating `rvc-vault/*` (all wiring names
  it: feedback auto-discovery `feedback.py` looks for the `rvc-vault/` sibling of the CLI,
  TEAMFLOW links target `RVC/rvc-vault/...`), we relocated only the marker: `git mv`
  `rvc-vault/.rvc-root` → `RVC/.rvc-root` (name stays `vault=rvc-vault`). The repo now matches
  STORY-037 exactly — vault in a named subdir, single marker at the project root — and
  resolution from root / inside the vault / subprojects is unchanged (verified). The empty
  `0-vault` was deleted and the symlinks restored. Lesson: `cmd init` must refuse to scaffold a
  second vault when a child owns an inner `.rvc-root`.

## 2026-09-29 — big-pickle — state pass: the wire is built, the sensor is dark; supply is the bottleneck
- **The measurement that reordered the vault.** With Avatar v0 shipped, its token configured, and
  its post-commit hook live in adlai-vault, the system has delivered **zero** messages:
  `avatar/.avatar-state.json` is `{"sent": {}}`. `rvc plate --format json` on *both* vaults reports
  `owes_turn: 0`, `owner: 0` — including read as the owner. The only live owed row anywhere is
  adlai-vault's hand-typed `00_INBOX/DISPATCH-SALWA-CORPUS-DEFECTS.md` (no `id:`, no `type:`, the
  plate renders it `type=—`). EPIC-004's founding claim — "there is no live wire between the state
  and the people" — was written that morning and is falsified by that evening. **Delivery was never
  the constraint; supply is.** Telegram is 200 lines of stdlib urllib and already works. Nothing
  mints an ask, so there is nothing to deliver. Adding forum topics and streaming drafts to a dark
  sensor builds a more sophisticated machine for transmitting zero.
- **EPIC-004 is now gated on STORY-039** (`gate: STORY-039` in frontmatter). The gate is one
  checkable line — a real delivery recorded in `.avatar-state.json` — not a vibe. This is the
  project's own lesson applied to itself: the arena died of formalism outrunning its participants,
  and EPIC-004's v1+ is that same move unless supply lands first.
- **STORY-039 is the next evolution.** It is the only open item that creates supply, and it is
  upstream of everything else: the plate's owed lanes (STORY-024), Avatar's inbound `/ask`, the
  grammar STORY-025 must derive, and any queue STORY-026 could ever drive. Its own AC5 — "four
  forever-zero lanes must be impossible to ship" — is the regression fixture this state proves was
  missing: those lanes sat at `[0]` for 13 days *underneath* shipped infrastructure built to serve
  them.
- **RVC's own plate is structurally degenerate, not merely empty.** `RVC/.rvc-root` declares no
  `alias.*` and no `plate.owner` (adlai-vault declares both), so `owes_turn` and `owner` can never
  be non-zero here — there is no identity to resolve against. This is STORY-024 AC3, unmade, and it
  means any measurement drawn from RVC's own plate reads a dead sensor. Landed with STORY-039
  (same files, and 039's AC5 fixture is exactly the cross-renderer agreement fixture 024 AC5 wants).
- **STORY-013 was cut from five criteria to one.** The index half (AC2/AC3) was a false premise:
  `rvc-vault` holds ~30 files, `adlai-vault` a few hundred, the plate renders in well under a
  second, and a persisted index would be a second source of truth needing invalidation on every
  transition. The `shell=True` half is not a hypothetical: it has 27 call sites and it already
  produced BUG-03 six hours before this pass. Security, not performance, is what was actually
  wrong.
- **`90_ARCHIVE/done/` contained a fix that never happened.** STORY-008 sat in the done archive
  with all four ACs unchecked, claiming `run_cmd()` was refactored; it was not. This is STORY-030's
  failure mode inverted and more dangerous — there a live bug was filed as fixed, here a dead fix
  was filed as live, in the one folder a reader trusts as settled history. Moved to
  `90_ARCHIVE/superseded/`, superseded by the rescoped STORY-013. **Lesson: an archive folder is a
  claim about the world, and claims rot silently.** A `done/` that is never audited is a liability
  with a reassuring name.
- **Four items deferred, each for a stated reason rather than a shrug.** EPIC-001 (a five-month-old
  wishlist pinned P0 at the top of the ready queue; two requirements already superseded, one an
  explicit anti-goal of the active epic). STORY-025 (normative R1–R10 is the learnable formalism
  that killed the arena; write it *after* the generator, derived from its output). STORY-030 (the
  incident that created it was closed the same day by `rvc feedback`; AC4 shipped better as
  `plate.source.*`; AC1 generalises one proven channel to N with exactly one counterexample — zero).
  STORY-014 (`pyyaml` would trade zero-dependency — load-bearing across the test runner, avatar,
  and the context engine — for a parsing edge case in a `0600` legacy script).
- **Deferral is recorded as re-entry conditions, not abandonment.** Every deferred story now states
  the observable that would bring it back. Two of them say the honest re-entry is *deletion*: if
  the owed lanes are still empty when STORY-026 is revisited, the right answer is to delete it, not
  to build it.

## 2026-11-06 — FEEDBACK-rvc round 2 (ADLAI letter)

- **Id minting scans the whole vault, not the tree.** The max-on-disk scan read only the
  tree's buckets, so an id resting in `90_ARCHIVE/FROM INBOX/` (named by no verb) could be
  minted twice — ids are permanent, and the floor (BUG-04) only remembers numbers nothing
  on disk remembers. `_next_id` now walks every directory: simpler than enumerating
  "every bucket", and the cost (a vault-wide walk under a lock) is the same order as
  `rescan`. BUG-05.
- **The plate renders every parked file.** `50_DEFERRED` non-issues were invisible (the
  `is_issue` gate), and the lane titled "deferred on purpose" actually showed `40_DECIDE`
  rulings. Kept the fold into one WAITING lane (a park and a ruling are both "not late",
  the load-bearing property), fixed the title to name both, and gave rows a
  `[40_DECIDE]`/`[50_DEFERRED]` bucket tag so a reader tells them apart. Rendering, not
  record: the folder stays the only state. BUG-06.
- **`--skip-ci` is a deprecated, warning alias.** The name inverted its own meaning
  (passing it *minted* a full pipeline). `--no-skip-ci`/`--ci` is the honest spelling;
  the old flag keeps working with a stderr note — operators' scripts must not break over
  a rename, and the warning teaches the inversion at the exact point of confusion.
  BUG-08.
- **Search: whole phrase → all-terms substring fallback → explained empty.** No stemmer
  (a dependency and a guess); the fallback is substring, so "filename" hits "filenames",
  and a bare "No results" now states which terms missed and to retry with fewer words.
  BUG-07.
- **Feedback is triaged per-item, not per-letter.** BUG-05..08 were minted individually
  (the letter's six already-resolved items were verified against existing tests instead
  of re-filed) and the letter itself was archived superseded with a resolution note —
  same shape as the round-1 letter. A re-ingested letter would double-file every fixed
  item.
- **Append-prone knowledge files grow in `##` sections.** The context benchmark caught a
  real trap this round: one long flat append to `GOTCHAS.md` (zero headings — one 9KB
  retrieval chunk) diluted it enough that the STORY-029 query lost it from top-5 and
  recall@5 fell to 77%. The BUG files and the archived letter were retrieval-neutral —
  isolated by reverting each delta in a scratch vault. Fix: new entries go under their
  own dated heading (a new chunk, not a longer old one). The ranker's b=1.0 length
  normalization stays as measured in STORY-033.
- **Two concurrency races surfaced while regression-testing round 2, both fixed (BUG-09).**
  The create lock's unlink-on-exit (STORY-130) let a retired-inode waiter run beside a
  fresh holder — duplicate minted ids, ~1 run in 3 with 8 forked creates, reproducible on
  the pre-session tree. And `bump_mint_floor`'s truncate-then-write marker could read as
  empty to the lock-free `resolve_tree`, silently resolving the LEGACY tree and filing
  an issue into `10_Issues/01_To_Do`. Fixes: inode recheck after flock acquisition
  (`_lock_path_is_current`) and atomic marker writes (`_atomic_write_text`). Both are
  stdlib-only and add no locks to the hot path. The concurrency test now scans for
  stray files outside the create bucket — per-path existence checks cannot see a
  wrong-bucket mint. Ids are permanent: a duplicate mint is the worst failure this
  tool has, so the stress harness (40 runs, zero flakes) is part of the regression.

## 2026-11-06 — pi (qwen3.8-flash) — the domain block is a histogram, and the name moves only its slug (BUG-14 review)

- **`rvc plate` DOMAINS is a per-slug histogram, not a listing.** The first cut grouped on the raw
  `domain_tags:` string, so every multi-tag issue became its own "domain" (`["rvc","protocol","story"] (1):
  <70-char filename>`) — a dump of the tag field, and the file names were already in the lanes above. Now:
  tags are parsed into slugs, an item joins every slug group it carries, and the render is `protocol×7
  rvc×4` + a folded ×1 tail + the untagged count. Detail stays in `--format json`. Same reason the plate
  titles a lane instead of explaining it: an index the eye can scan, not a table to read.
- **One fact, read one way.** `parse_domain_tags` / `frontmatter_domain_tags` (core.py) are the only readers
  of the field, shared by plate, doctor and context — scalar, flow list, quoted flow list and YAML block list
  all mean the same thing to all three. Divergent readers are how a tag decays: the vault's own 47 tagged
  files use three different shapes.
- **`rvc set --domain` mutates only the slug in the file name.** The first cut rebuilt the whole name from
  `issue_id + title`, so changing a *priority* silently renamed any file whose name had drifted from its
  title — and healed wikilinks to match. A rename is the history-breaking half of this feature (the letter
  said so before it was built), so the blast radius is now exactly the trailing `[slug]`.
- **Ask 3's vocabulary lives in `.rvc-root` (`domain.<slug>=<what it covers>`) and is checked by the plate,
  not by `create`.** The first pass read a hardcoded `10_CONTEXT/specs/Story-Domains.md`, made it mandatory,
  was reverted, and left the helper dead. Both halves were wrong: a separate vocabulary file is a second place
  to remember and prose needs a parser that will disagree with itself, while refusing a mint turns a typo into
  a blocked session. The marker already owns everything machine-readable about a vault (`tree.<verb>`,
  `mint.<PREFIX>`, `alias.*`, `plate.source.*`), so the list is one more key there and the plate names what is
  off-list. No `domain.` lines means no rule — and the plate says `vocabulary: none declared`, so an unchecked
  tag set is never read as a clean one.
