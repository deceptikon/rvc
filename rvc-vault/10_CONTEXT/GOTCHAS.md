# GOTCHAS — Non-obvious Bugs & Environment Traps (rvc-vault)

- **A transition on a never-committed issue is a plain move, and that is fine.** `rvc issue
  <ID> start|done` on a `??` deposit prints `[RVC] <name> is untracked — plain move` and commits
  the moved file — no `git mv` rename is recorded (there was nothing to rename). History for such
  files starts at the transition commit; the deposit itself was never in git.
- **`sync_before` skips the pull when the working tree is dirty.** `git pull --rebase` aborts on
  any unstaged change, so a dirty tree (e.g. an untracked deposit) always produced a scary
  `cannot pull with rebase: You have unstaged changes` on every transition. Now the pull is simply
  skipped with a one-line notice; run `git pull` by hand after clearing the tree.
- **`.rvc-create.lock` is a flock, not a pid file — and now it is gone after success.** The
  `pid=` line inside is diagnostic only; the flock is authoritative (a crashed holder's flock is
  released by the kernel). Since STORY-035 the marker is removed on a clean exit, and a leftover
  stale `pid=` is reclaimed with an explicit notice. Never trust a leftover `.rvc-create.lock` as
  "locked" — it is stale by definition.
- **`rvc` on PATH** is the folder-as-state CLI (symlink → `~/X/TEAMFLOW/RVC/rvc-cli.py`).
  If that symlink ever points elsewhere (it used to target the parked plate-based "RVC 0-point"
  engine at `~/W/RVC_reload/rvc.py`), re-run `python3 rvc-cli.py install --force`.
  `session_bootstrap.sh`-style contracts should keep calling `$RVC_BIN` explicitly.
- **`rvc-vault/10_Issues` legacy paths are gone** — the repo's vault moved to the newvault tree
  (2026-09-13). Old links like `10_Issues/01_To_Do/...` resolve only through git history.
- **`find_vault_root` walks up 8 levels from CWD.** Running `rvc` inside a sibling vault can
  accidentally pick up that vault — verify with `--path` when unsure.
- **`rvc-cli.py` is not importable by its filename** (hyphen). The local test suite loads it via
  `importlib` in `tests/helpers.py` under the module name `rvc_cli` — tests must use that loader, not
  a plain `import rvc_cli`.
- **Minted ids before STORY-028 had no `id:`/`title:`.** Existing CLI-minted tickets (e.g. ADLAI
  `STORY-107/108/109`) still lack the `id:` field — re-mint or `rescan` to normalize; the filename is
  no longer the only identity carrier for new issues.
- **`rvc doctor` rewrites only the frontmatter block, never the body.** `_doctor_rewrite` operates on
  the lines between the opening and closing `---`; a file without a frontmatter block passes through
  untouched. It is deliberately surgical — a full `rescan` (wikilinks + tag inference) is a separate,
  broader operation that can churn files far beyond constitution hygiene.
- **`vault-restructure.py`'s normalizer now depends on the vault's tree shape.** On a tree that
  declares `tree.block=` it *deletes* `status:` instead of normalizing it; stray tiers (`P0.0.0`)
  fold to their base tier. Legacy trees (no block) keep the old normalize-status behavior — running
  `rescan` on a legacy vault will not strip `status:`.
- **A `status:` merged in via `extra_frontmatter` on a block-bucket tree now hard-fails.** Callers
  (MCP layer, integrations) that minted one field-line greps passed since folder-owns-state was only
  enforced in the frontmatter builder. The create path refuses with exit 1 — catch `SystemExit` in
  callers that talk to `cmd_create_issue` directly.
- **`rvc context` soft results are policy-ranked, not raw BM25.** Archive buckets (`tree.evict` /
  `tree.supersede`) are indexed but never suggested, and docs under `tree.roadmap` (`10_CONTEXT`)
  carry a ×1.5/×1.2 prior; `b=1.0` length normalization is deliberate. Changing any of these moves
  the hand-labeled benchmark — `tests/test_context_benchmark.py` pins recall@5 ≥ 80% (currently 92%,
  measured on a scratch copy of the live vault, never the vault itself).
- **The context cache is keyed by Document ID, and colliding ids last-win.** Two files carrying the
  same `id:` frontmatter (or the same `PREFIX-NN` filename shape) collapse into one document in
  `.rvc-context-cache.json`; `rvc doctor` does not audit identity collisions (yet).
- **`rvc issue <ID> triage` gate: non-issue types are refused, exit 1.** A deposit whose frontmatter
  `type:` is not story/epic/bug/task (`proposal`, `feedback`, …) cannot be triaged into the queue —
  the CLI warns `manual placement required` and does not move it. Place those by hand (or `block` /
  `supersede` them, which still route any file).
- **`sync_after` commits via a throwaway index; operator-staged work survives untouched.** RVC
  commits only the moved/created paths (STORY-034 AC2). If you stage work *before* running an `rvc`
  transition, it stays staged and never crosses into the RVC commit — verify with
  `git diff --cached` afterwards.
- **`rvc plate --write` regenerates PLATE.md from the tree.** The file at `tree.roadmap/PLATE.md`
  (`10_CONTEXT/PLATE.md` on newvault) is a rendering, not a record — refresh it after transitions;
  hand-editing it is the one thing the constitution forbids.