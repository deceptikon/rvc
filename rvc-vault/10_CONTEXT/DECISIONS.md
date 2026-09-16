# DECISIONS — Architectural Decisions (rvc-vault)

Format: `## <date> — <agent> — <title>` + 2–4 lines of rationale. Never delete the *why* of a
live decision; compress superseded ones to one line pointing at the resolving commit/story.

- Dogfooding note: this vault moved to the **newvault** tree on 2026‑09‑13 (`rvc project init
  --tree newvault`), legacy content migrated by `git mv`, root `README.md` regenerated from
  `README_TEMPLATE`. Deep specs: `10_CONTEXT/specs/DECISION-Domain-Structuring.md` (domain
  structuring rationale) and `10_CONTEXT/specs/PROTOCOL.md`.

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