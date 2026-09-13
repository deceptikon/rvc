# RVC — folder-as-state vault engine

`rvc-cli.py` manages **RVC vaults**: lightweight, git-tracked issue & knowledge vaults where
**the folder an issue sits in *is* its status.** A single stdlib-only script, no other
dependencies.

- **Folder = state.** Transitions (`start`, `done`, `block`, `evict`, …) are plain `git mv` —
  recoverable through git history, greppable, no frontmatter drift.
- **Per-vault config.** `.rvc-root` may carry `tree.<verb>=<dir>` lines; unconfigured vaults
  keep working on the legacy `10_Issues` map.
- **Self-installing.** No pip package — `rvc` on PATH is a symlink to this script.

## Install

```bash
git clone git@github.com:deceptikon/rvc.git
cd rvc
python3 rvc-cli.py install        # → ~/.local/bin/rvc (idempotent)
rvc install --check               # verify
```

## Quickstart — RVC-fy a new project

```bash
mkdir myproject && cd myproject
git init                          # transitions are git mv — git is the safety net
rvc project init . --tree newvault   # creates vault/ + README.md at the project root
rvc create "First idea"           # lands in 20_NEXT
rvc issue list                    # see it
rvc issue STORY-01 start          # → 30_ACTIVE (git mv)
rvc issue STORY-01 done           # → 60_DONE
```

`project init` also writes a **generic README.md at the project root** pointing at the vault
layout, the daily commands, and the constitution — the obvious place to look next for anyone
opening the project. Never overwrites an existing README.

## Vault trees

| Preset | Layout | Constitution |
|--------|--------|--------------|
| `newvault` | `00_INBOX 10_CONTEXT 20_NEXT 30_ACTIVE 40_DECIDE 50_DEFERRED 60_DONE 90_ARCHIVE/{done,superseded}` | `vault/10_CONTEXT/ROUTING.md` |
| `legacy` | `00_Project 10_Issues/{00_Backlog..04_Done} 20_Specs 90_Assets 99_Archive` | `vault/00_Project/REGLAMENT.md` |

## Documentation

- **`rvc-vault/20_Specs/PROTOCOL.md`** — the protocol: structure, CLI usage, lifecycle, git discipline.
- **`rvc-vault/00_Project/`** — roadmap and decisions.
- Live contract reference: ADLAI (`~/X/ADLAI/adlai-vault/`) runs on the `newvault` tree,
  TEAMFLOW/conductor/dash on the legacy fallback.