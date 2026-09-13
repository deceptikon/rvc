---
domain: workflow_meta
domain_tags: ["rvc", "protocol"]

# RVC Revival Plan — Locked Decisions

> Session: 2026-06-30. Status: **tooling locked, domain model pending.**

---

## 1. Vault Location

**Always `.RVC/` in project root.** Single canonical location. No flat vs nested ambiguity.

```
~/Q/myproject/
├── .RVC/                     ← canonical vault (hidden)
│   ├── rvc.toml              ← name, protocol_version, created_at
│   ├── .obsidian/            ← Obsidian config
│   ├── issues/               ← one .md per issue, status in frontmatter
│   ├── specs/                ← architecture, PRDs, guides
│   ├── artifacts/            ← per-story run artifacts
│   └── meta/                 ← reglament, state, decisions, gotchas
├── myproject -> .RVC/        ← symlink (Obsidian opens this, sees "myproject")
├── src/
└── pyproject.toml
```

**Why:**
- Discovery trivial: `find .RVC/` — no 8-level climbing, no heuristics.
- No status folders. Status is frontmatter-only. Eliminates dual source-of-truth bugs.
- Hidden by default, git-tracked.
- Conductor config: `vault = "~/Q/ADLAI/.RVC"` — always the same pattern.

---

## 2. Vault Structure (4 flat buckets)

| Dir | Purpose |
|-----|---------|
| `issues/` | Issue tracking. Status in frontmatter, not folder. |
| `specs/` | Architecture, PRDs, guides. Flat. |
| `artifacts/` | Per-story run artifacts (prompts, stdout, runs). |
| `meta/` | `REGLAMENT.md`, `STATE.json`, `DECISIONS.md`, `GOTCHAS.md`. |

**Killed:**
- `00_Project/`, `10_Issues/`, `20_Specs/`, `90_Assets/`, `99_Archive/` — replaces with flat names.
- `00_Backlog/`, `01_To_Do/`, `02_Active/`, `03_Review/`, `04_Done/` — status folders gone.
- `MAP.md` — gone. In-memory index only. No static graph file.
- `DASHBOARD.canvas` — Obsidian's problem, not RVC's.

---

## 3. Metadata File

`.RVC/rvc.toml`:
```toml
[protocol]
version = 2
name = "adlai"
created = "2026-07-01"
```

No vault linking yet — don't touch what isn't causing trouble.

---

## 4. Init Command

```
rvc init [path] [--name N]
```

Creates `.RVC/` + 4 dirs + symlink. Name defaults to basename of `path`.

---

## 5. MCP Tools (5 grouped)

| Tool | Capabilities |
|------|-------------|
| `rvc_issue` | get, create, list, start, review, done, validate |
| `rvc_context` | assemble issue + linked specs + deps, depth-limited |
| `rvc_search` | full-text grep across vault |
| `rvc_artifact` | list, get, save |
| `rvc_vault` | info, init, link |

LLMs see 5 tools, clear domains. No confusion.

---

## 6. Critical Fixes (P0)

| Issue | Fix |
|-------|-----|
| `shell=True` in `run_cmd()` | Replace with list-based `subprocess.run`. |
| Frontmatter parser breaks on `:` in values | Proper YAML parser for frontmatter blocks. |
| Auto-git commit/push destructive | Gate behind `--git` flag. Default: no git ops. |
| `git rm` wrong relative path | Compute path from git root, not vault root. |
| `vault-restructure.py` (hyphen, can't import) | Rename to `vault_restructure.py`. |
| Duplicate `rvc_mcp.py` in GATHERING | Deprecate. Point MCP configs to `rvcd.py`. |
| Hardcoded "ADLAI" in MAP header | Goes away with MAP.md removal. |
| `EPIC_RE` comment lies about range | Fix comment. |
| Status/directory mismatch on `rvc create --dir 02_Active` | Goes away with flat structure. |

---

## 7. Repackaging

Move from loose scripts to `rvc/` package:

```
rvc/
├── __init__.py
├── cli.py              ← rvc-cli.py
├── daemon.py           ← rvcd.py
├── restructure.py      ← vault_restructure.py
├── sync.py             ← rvc-sync.py
├── context.py          ← new: context engine
├── vault.py            ← new: vault operations
├── frontmatter.py      ← new: YAML frontmatter
└── paths.py            ← new: centralized path resolution
```

Add `[project.scripts]` to `pyproject.toml`:
```toml
[project.scripts]
rvc = "rvc.cli:main"
rvcd = "rvc.daemon:main"
```

---

## 8. Migration

```
rvc vault migrate [path]
```

Detects old vault structure (flat with `00_Project/`, `10_Issues/`, etc.), moves into `.RVC/`, creates symlink. Preserves all content, rewrites frontmatter paths.

---

## 9. Git

**Tracked by default.** `.RVC/` is NOT in `.gitignore`. Git ops are opt-in via `--git` flag on issue transitions.

---

## DECIDED: Domain-Based Structuring

The domain model has been decided. See `[[DECISION-Domain-Structuring]]` for the full specification covering domain declaration, story-to-domain binding, context scoping, cross-domain references, and granularity policy.
