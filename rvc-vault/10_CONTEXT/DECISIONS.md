# DECISIONS — Architectural Decisions (rvc-vault)

Format: `## <date> — <agent> — <title>` + 2–4 lines of rationale. Never delete the *why* of a
live decision; compress superseded ones to one line pointing at the resolving commit/story.

- Dogfooding note: this vault moved to the **newvault** tree on 2026‑09‑13 (`rvc project init
  --tree newvault`), legacy content migrated by `git mv`, root `README.md` regenerated from
  `README_TEMPLATE`. Deep specs: `10_CONTEXT/specs/DECISION-Domain-Structuring.md` (domain
  structuring rationale) and `10_CONTEXT/specs/PROTOCOL.md`.

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