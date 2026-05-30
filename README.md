# RVC — Reglament of Vault Context

Local-first, Obsidian-native issue tracking protocol for AI-assisted development.

## What is RVC?

RVC is a CLI tool + MCP daemon that treats an Obsidian vault as a project management system. Issues are Markdown files with YAML frontmatter, organized by status folders. AI coding assistants (Qwen Code, Cursor) interact through MCP tools; humans interact through Obsidian or the CLI.

## Architecture

```
┌── Human ──────────┐    ┌── AI Assistant ───────┐
│  Obsidian GUI     │    │  Qwen Code / Cursor   │
│  rvc CLI (shell)  │    │  MCP protocol         │
└────────┬──────────┘    └───────────┬───────────┘
         │                           │
    ┌────▼───────────────────────────▼────┐
    │           rvc-cli.py                │
    │  find_vault_root() → 10_Issues/     │
    └─────────────────────────────────────┘
         ▲
    rvcd.py (FastMCP daemon, stdio)
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
├── 00_Project/        # ROADMAP.md, REGLAMENT.md, DASHBOARD.canvas
├── 10_Issues/
│   ├── 00_Backlog/    # Ideas, unrefined
│   ├── 01_To_Do/      # Prioritized, ready to start
│   ├── 02_Active/     # In progress
│   ├── 03_Review/     # Awaiting approval
│   └── 04_Done/       # Completed
├── 20_Specs/          # Architecture docs, PRDs, reviews
├── 90_Assets/         # Media, PDFs
└── 99_Archive/        # Deprecated notes
```

### Initialize a New Vault

```bash
# Use a custom vault name (for Obsidian vault switcher distinguishability)
rvc project init --vault-name myproject-vault /path/to/project

# Creates: myproject-vault/.rvc-root + all standard directories
```

## CLI Usage

```bash
# ── Issue Lifecycle ──
rvc issue list                  # List all issues
rvc issue list To Do            # Filter by status
rvc issue STORY-28              # Read an issue
rvc issue STORY-28 start        # To Do → Active
rvc issue STORY-28 review       # Active → Review
rvc issue STORY-28 done         # Review → Done

# ── Create Issues ──
rvc create "My New Feature"
rvc create "Critical Bug" --prefix BUG --type bug --priority Critical
rvc create "Spike: Reranker" --epic EPIC-05-PRD-Phase-2 --body "## Context\n..."

# ── Context Assembler ──
rvc context STORY-28            # Loads issue + all [[linked]] specs

# ── Search ──
rvc search "pgvector"           # Case-insensitive vault grep

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

## MCP Daemon

`rvcd.py` exposes RVC as MCP tools for AI assistants:

```bash
# Start via stdio (for Qwen Code / Cursor integration)
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

All tools accept `project_path` — the absolute path to the project root — so a single daemon can serve multiple projects.

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

## License

Internal tooling for ADLAI and related projects.
