# RVC — Obsidian-Native Issue Tracker (CLI + MCP)

RVC (Ritual Vault Context) is the context engine and issue tracker for the X Workspace. Manages STORY-XX, EPIC-XX, BUG-XX, and TASK-XX issues across vaults. Provides `rvc get`, `rvc context`, `rvc create`, and `rvc issue` CLI commands plus an MCP server.

## Quick Start

```bash
cd ~/X/TEAMFLOW/RVC && uv run python rvc-cli.py issue list
cd ~/X/TEAMFLOW/RVC && uv run python rvc-cli.py create "Title" --prefix STORY
cd ~/X/TEAMFLOW/RVC && uv run python rvc-cli.py issue STORY-XX start
```

## Key Docs

- [[PROTOCOL.md]] — RVC protocol specification
- [[REGLAMENT.md]] — Vault reglament
- [[OBSIDIAN_TEMPLATER.md]] — Obsidian template conventions
- [[HANDOVER.md]] — Domain-based vault structuring handover

## Parent

- [[../../../AGENTS.md|Root AGENTS.md]] — X Workspace entry point
