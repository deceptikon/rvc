- 2026-09-29 (STORY-142): `rvc issue <ID> start|done` fails its atomic `git mv` on filenames containing an apostrophe (`STORY-142-…self-disclaimed-'general-information'…`) — "fatal: bad source", falls back to a plain move. The transitions still landed, but state was briefly ambiguous (`AD` in the index until a manual add). Either quote the paths in the mv, or warn loudly when falling back.
- 2026-11-05 (STORY-142, reproduced): same apostrophe bug, sharper failure — after the `git mv` fallback, the "Committing state..." step staged the *mangled* (apostrophe-stripped) path, committed nothing, and reported success: HEAD unchanged, story file left deleted-unstaged in `20_NEXT/` and untracked in `30_ACTIVE/`. Reproduce: `rvc issue STORY-142 start` on a repo whose remote is unreachable (the preceding `git pull --rebase` failed on DNS, which may be a second, independent contributor). Operator had to notice via `git status` and hand-commit the transition.
- 2026-11-05 (STORY-142 session): `rvc rescan` rewrote 230 files vault-wide (frontmatter tags, wikilinks, and prose reformatting reaching `10_CONTEXT/` always-load files and `PLATE.md`) when the operator only wanted a search-cache refresh — `context <ID> --reindex` is the narrow tool for that. Rescan should print its write scope before rewriting, or grow a `--dry-run`. Reverted from the STORY-142 MR to keep the diff atomic.
- 2026-11-05 (STORY-154 filing): `rvc create` minted STORY-153 while STORY-153 already existed in `90_ARCHIVE/FROM INBOX/` — the max-on-disk ID scan does not cover the archive's FROM INBOX subfolder, so newly minted ids can collide with archived ones (ids are supposed to be permanent). Had to hand-rename the fresh issue to STORY-154 and amend the create commit before push. Scan every bucket for the max id, or refuse to mint an id that already exists anywhere on disk.
- 2026-11-05 (plate blind spot, first seen at session SYNC): `50_DEFERRED/` items appear on NO plate lane. Measured: `50_DEFERRED/ESSAY--The-Pilot-and-the-Prison-Guard.md` exists but renders nowhere — the plate showed "WAITING — deferred on purpose [0]" with the essay parked; after blocking STORY-157, that same lane renders the `40_DECIDE/` item instead. So the lane labelled "deferred on purpose" actually shows blocked-on-ruling items, while the bucket that IS deferred on purpose is invisible. A parked item the plate cannot see is exactly the blind-spot class rvc exists to kill: render `50_DEFERRED` as its own lane (or fold it into WAITING with a bucket tag) and relabel the 40_DECIDE lane.
- 2026-11-05 (search matching): multi-word queries behave as an exact-token AND with no stemming or substring fallback, and "No results" does not say why — `rvc search "apostrophe filename"` returned nothing (the file says "filenames", not "filename") while `rvc search "apostrophe"` returned 3 matches a second earlier on the same cache. Suggest stemming/substring fallback, or at least a hint to retry with fewer words.
- 2026-11-05 (flag naming): `--skip-ci` on `create` and issue transitions DISABLES the `[skip ci]` stamp ("disable [skip ci] in the commit message (default: enabled)") — the name reads as "make this commit skip CI", which is the opposite of what it does. Someone wanting a quiet vault commit who passes `--skip-ci` will mint a full pipeline instead. Rename (e.g. `--no-skip-ci` or `--ci`) or make the help line lead with the inversion.

- 2026-11-05 (GLM, STORY-140/154 session): every `rvc issue … start/done` in a tree with any unrelated unstaged change prints `Warning: Git pull failed: … Please commit or stash them` before proceeding correctly. The move+commit always landed fine, but the error-shaped warning reads like a failed transition. Consider detecting "rebase impossible due to unstaged changes but branch is local-only / nothing to pull" and saying that instead, or scoping the sync to the vault paths it actually needs.

- 2026-11-05 (EPIC-11 scaffold): `rvc create --type epic` keeps the default `STORY` id prefix — it minted `STORY-159-FE-Design-Handoff.md` (frontmatter `type: epic`, id STORY-159) instead of an `EPIC-<n>` id; `--prefix EPIC` must be passed separately to get the epic series. Consider deriving the prefix from `--type`, or warning when type and prefix disagree. Cleanup: removed the misfire (`1441764`) and recreated as EPIC-11.
- 2026-11-05 (EPIC-12 create): `rvc create --body` prepends its own generated `# <ID>: <title>` heading, so a body that opens with that same heading lands duplicated — `EPIC-12-FE-design-backend-contracts.md` shipped with two identical H1s and needed a manual fix after the create commit had already landed. Either drop a leading H1 that matches the generated one, or document that `--body` is prose-only. Follow-up to the entry above, now confirmed working: `rvc create "…" --prefix EPIC --type epic` minted EPIC-12 with correct frontmatter, and `_next_id`'s per-prefix scan numbers epics independently of the STORY series; `rvc issue <ID> triage` is a real verb and the plate's INBOX lane does list both epics, so neither is a defect.

---

# Resolution (2026-11-06, RVC)

Checked against `feature/sqlite-context-cache`, not master (the branch the letter was
written against). Six of the ten items were already resolved upstream and verified by
existing tests: apostrophe `git mv` (BUG-03), mangled-path staged commits (STORY-034
scoped temp-index commits), `rescan --dry-run` + `reindex`, quiet pull-skip on dirty
trees (FEEDBACK 2026-09-17/18), type-derived prefixes (BUG-04), `--body` H1 dedup.

The four unresolved items were fixed and regression-tested as **BUG-05** (mint scan
walks the whole vault — no more id collisions with `90_ARCHIVE/FROM INBOX/`),
**BUG-06** (every parked file renders; waiting rows carry 40_DECIDE/50_DEFERRED
bucket tags; lane title names both), **BUG-07** (search whole-phrase → all-terms
substring fallback; empty results say why), **BUG-08** (`--no-skip-ci`/`--ci` run CI;
`--skip-ci` kept only as a warned, deprecated alias).

Suite: 121 passed, 0 failed, 1 skipped.
