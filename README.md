# RVC

Managed with **RVC** — a lightweight, folder-as-state issue & knowledge vault at `rvc-vault/`.

> **State lives in folders, not frontmatter.** Where an issue file sits *is* its status.

## Where to look next

| Path | What it is |
|------|-----------|
| `rvc-vault/.rvc-root` | Vault marker + `tree.<verb>=<dir>` map for this vault |
| `rvc-vault/10_CONTEXT/ROUTING.md` | The constitution — bucket law, triage rules, session protocol |
| `rvc-vault/10_CONTEXT/DECISIONS.md` | Architectural decisions and their rationale |
| `rvc-vault/10_CONTEXT/GOTCHAS.md` | Non-obvious bugs and environment traps |
| `rvc-vault/10_CONTEXT/STATE.json` | Current active issue / session state |
| `rvc-vault/` | Lifecycle buckets (new vaults: 00_INBOX … 90_ARCHIVE; legacy: 10_Issues) |

## Commands

```bash
rvc issue list              # everything open
rvc issue create "First"    # idea → inbox
rvc issue STORY-01 start    # → active (a git mv under the hood)
rvc context STORY-01        # pull linked context
rvc issue STORY-01 done     # → done
```

Transitions are plain `git mv`, so every move is recoverable through git history.

## Protocol

Read `rvc-vault/10_CONTEXT/ROUTING.md` first — it overrides the rest of this file.
