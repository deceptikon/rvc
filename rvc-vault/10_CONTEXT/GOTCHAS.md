# GOTCHAS — Non-obvious Bugs & Environment Traps (rvc-vault)

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