> **Active Epic:** [[EPIC-001-RVC-Protocol]]

---
domain: workflow_meta
domain_tags: ["rvc", "protocol"]

# RVC — Reglament of Vault Context

Local-first, Obsidian-native issue tracking protocol for AI-assisted development.

## What is RVC?

RVC is a CLI tool + MCP daemon that treats an Obsidian vault as a project management system. Issues are Markdown files with YAML frontmatter, organized by status folders. AI coding assistants interact through MCP tools; humans interact through Obsidian or the CLI.

## Architecture

```
┌── Human ──────────┐    ┌── AI Assistant ───────┐    ┌── Background ────┐
│  Obsidian GUI     │    │  Qwen Code / Cursor   │    │  cron (rescan)   │
│  rvc CLI (shell)  │    │  Hermes (TUI/CLI)     │    │  every 6 hours   │
│                   │    │  MCP protocol         │    └────────┬─────────┘
└────────┬──────────┘    └───────────┬───────────┘             │
         │                           │                         │
    ┌────▼───────────────────────────▼─────────────────────────▼────┐
    │                      rvc-cli.py                                │
    │              find_vault_root() → 10_Issues/                    │
    │                  vault-restructure.py                          │
    │        (rescan: frontmatter, wikilinks, tags, MAP.md)         │
    └──────────────────────────────┬────────────────────────────────┘
                                   ▲
                              rvcd.py
                   (FastMCP daemon, stdio or SSE)
```

## Install

The CLI is a single Python file — no installation needed beyond making it executable:

```bash
# Option 1: Symlink (recommended — updates automatically)
ln -s $(pwd)/rvc-cli.py ~/.local/bin/rvc

# Option 2: Copy
cp rvc-cli.py ~/.local/bin/rvc

# Verify
rvc --help
```

For the MCP daemon, install the `mcp` dependency:

```bash
pip install 'mcp>=1.6.0'
# or with uv:
uv sync   # uses pyproject.toml
```

## Vault Structure

Every project vault must follow this layout:

```
<project>-vault/
├── .rvc-root          # Marker file (enables vault discovery)
├── .obsidian/         # Obsidian config + plugins
├── 00_Project/
│   ├── MAP.md         # Auto-generated knowledge graph index
│   ├── ROADMAP.md     # Project roadmap
│   ├── REGLAMENT.md   # Project rules/conventions
│   └── DASHBOARD.canvas # Obsidian canvas
├── 10_Issues/
│   ├── 00_Backlog/    # Ideas, unrefined
│   ├── 01_To_Do/      # Prioritized, ready to start
│   ├── 02_Active/     # In progress
│   ├── 03_Review/     # Awaiting approval
│   └── 04_Done/       # Completed
├── 20_Reviews/        # Audit reports, critical reviews
├── 20_Specs/          # Architecture docs, PRDs
├── 90_Assets/         # Media, PDFs
└── 99_Archive/        # Deprecated notes
```

### Initialize a New Vault

```bash
# Use a custom vault name (for Obsidian vault switcher distinguishability)
rvc project init --vault-name myproject-vault /path/to/project

# Creates: myproject-vault/.rvc-root + all standard directories
```

---

## CLI Usage

All commands auto-discover the vault from your current directory (or use `--path`).

```bash
# ── Issue Lifecycle ──
rvc issue list                  # List all issues
rvc issue list "To Do"          # Filter by status: Backlog, To Do, Active, Review, Done
rvc issue STORY-28              # Read an issue
rvc issue STORY-28 start        # To Do → Active
rvc issue STORY-28 review       # Active → Review
rvc issue STORY-28 done         # Review → Done

# ── Create Issues ──
rvc create "My New Feature"
rvc create "Critical Bug" --prefix BUG --type bug --priority Critical
rvc create "Spike: Reranker" --epic EPIC-05-PRD-Phase-2 --body "## Context\n..."

# ── Context Assembler ──
rvc context STORY-28            # Loads issue + all [[linked]] references

# ── Search ──
rvc search "pgvector"           # Case-insensitive vault grep

# ── Vault Rescan (maintenance) ──
rvc rescan                      # Normalize frontmatter, wrap STORY/EPIC links, infer tags, update MAP.md
rvc rescan --dry-run            # Preview changes without writing
rvc rescan --skip-map           # Skip MAP.md regeneration

# ── Project Info ──
rvc project info                # Show vault path + ROADMAP.md
```

### Create Command Options

| Flag | Default | Description |
|------|---------|-------------|
| `--prefix` | `STORY` | ID prefix (STORY, BUG, TASK, EPIC) |
| `--type` | `story` | Issue type |
| `--priority` | `Medium` | Low, Medium, High, Critical |
| `--body` | _(template)_ | Initial body text (`\n` for newlines) |
| `--dir` | `01_To_Do` | Target folder under `10_Issues/` |
| `--epic` | _(none)_ | Parent epic name |

---

## Vault Rescan — What It Does

`rvc rescan` (and `rvc_rescan_vault` via MCP) is the vault's self-healing command. Run it after creating new issues, or set up a cron job to keep everything structured.

### Actions performed

1. **Frontmatter normalization** — ensures every `.md` file has consistent `type`, `id`, `title`, `status`, `priority`, `epic`, and `tags` fields.
2. **Wikilink auto-wrapping** — finds plain-text `STORY-XX` and `EPIC-XX` references and wraps them in `[[wikilinks]]` so the graph connects.
3. **Domain tag inference** — adds tags like `#retrieval`, `#llm`, `#eval`, `#infra`, `#citation`, `#routing`, `#ingestion`, `#frontend`, `#vertical`, etc. based on content keywords.
4. **MAP.md regeneration** — generates a navigable knowledge graph index at `00_Project/MAP.md` with:
   - Epics and stories grouped by status
   - Domain tag index
   - Cross-reference graph (`[[SRC]] → [[TGT]]`)

### Idempotent

Safe to run repeatedly — no duplicate wikilinks, no re-tagging of already-correct files. Zero wikilinks added on a re-run means the vault is fully structured.

### Cron setup

```bash
# Every 6 hours
0 */6 * * * cd /path/to/project && rvc --path vault-dir rescan
```

---

## MCP Daemon

`rvcd.py` exposes RVC as MCP tools for AI assistants:

```bash
# Start via stdio (for Qwen Code / Cursor / Hermes integration)
uv run rvcd.py

# Or SSE mode for network access
uv run rvcd.py --sse --port 8080
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `rvc_get_issue` | Read an issue by ID |
| `rvc_get_context` | Load issue + all linked references |
| `rvc_issue_list` | List issues, optionally filtered by status |
| `rvc_issue_start` | Transition to Active |
| `rvc_issue_review` | Transition to Review |
| `rvc_issue_done` | Transition to Done |
| `rvc_create_issue` | Create a new issue with frontmatter |
| `rvc_search_vault` | Search vault .md files |
| `rvc_rescan_vault` | Rescan vault: normalize, link, tag, regenerate MAP.md |

All tools accept `project_path` — the absolute path to the project root — so a single daemon can serve multiple projects.

### Hermes Integration

Hermes auto-discovers the MCP server if configured in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  rvcd:
    command: /home/lexx/Q/conductor/.venv/bin/python
    args:
      - /home/lexx/Q/vault-protocol/rvcd.py
    enabled: true
```

After a session reload (or restart), all 9+ tools appear in your tool list. You don't call `uv run conductor` — Hermes handles MCP lifecycle automatically via its internal `mcp_tool.py`.

### Qwen Code Configuration

Add to `~/.qwen/settings.json`:

```json
{
  "mcpServers": {
    "rvc": {
      "command": "uv",
      "args": ["--directory", "/path/to/vault-protocol", "run", "rvcd.py"],
      "timeout": 3600,
      "alwaysAllow": [
        "rvc_create_issue",
        "rvc_issue_start",
        "rvc_issue_review",
        "rvc_issue_done"
      ]
    }
  }
}
```

---

## How Models Use The Vault

LLMs traverse the vault like this:

```
1. rvc context STORY-83       ← load issue + all [[linked]] stories/epics/specs
2. rvc search "chunking"      ← find relevant docs by keyword
3. rvc issue list "Active"    ← see what's in progress
4. MAP.md                     ← start here: full project index with cross-references
5. rvc rescan                 ← keep the graph healthy (cron or manual)
```

The graph flows: **MAP.md → EPIC → STORY → linked stories/specs**. Domain tags let models filter by concern without reading every file.

---

## Vault Discovery

`find_vault_root()` locates the vault by checking (in order):

1. `.rvc-root` marker file in current or parent directory
2. Child directory containing both `10_Issues/` and `.obsidian/`
3. Child directory literally named `vault` (backward compat)

This allows vaults to use any directory name — critical when you have multiple projects open in Obsidian's vault switcher.

## Git Sync

The CLI optionally syncs with a remote after transitions:
- **Pre-transition**: `git pull --rebase`
- **Post-transition**: `git add + commit + push`

This is best-effort — failures produce warnings, not errors.

## Vault-Restructure Python API

For programmatic use:

```python
from vault_restructure import rescan_vault

summary = rescan_vault("/path/to/vault", dry_run=False, skip_map=False)
# Returns: {
#     "files_processed": 114,
#     "files_changed": 3,
#     "wikilinks_added": 12,
#     "map_path": "/path/to/vault/00_Project/MAP.md",
#     "results": [...]
# }
```

---

## License

Internal tooling for ADLAI and related projects.



## Sub-Documents & Context
- [[RVC/OBSIDIAN_TEMPLATER]]
- [[RVC/rvc-vault/00_Project/PLAN-RVC-REVIVAL]]
- [[rvc-vault/10_Issues/01_To_Do/EPIC-001-RVC-Protocol|EPIC-001]]
- [[rvc-vault/10_Issues/01_To_Do/EPIC-002-Conductor-v0.2-Hardening|EPIC-002]]
