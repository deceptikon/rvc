# Reglament of Vault Context (RVC) v1.0

## 1. Philosophy
The vault is the primary source of truth for all project context, decisions, and issues.
- **Local-First:** All context is in Markdown.
- **Human-AI Collaboration:** Standardized metadata ensures both humans and LLMs can parse and update the state.
- **Graph-Oriented:** Bi-directional links (`[[]]`) map the dependency graph.

## 2. Directory Structure
All project vaults MUST follow this core hierarchy:

- `00_Project/`
  - `DASHBOARD.canvas` - The visual command center.
  - `ROADMAP.md` - High-level goals.
  - `REGLAMENT.md` - Project-specific overrides.
- `10_Issues/`
  - `00_Backlog/` - New ideas, unrefined tasks.
  - `01_To_Do/` - Refined and prioritized.
  - `02_Active/` - Currently being worked on.
  - `03_Review/` - Pending approval/testing.
  - `04_Done/` - Completed.
- `20_Specs/`
  - `Architecture/` - System design and diagrams.
  - `PRDs/` - Requirements for large features.
  - `Guides/` - Developer and user documentation.
- `90_Assets/` - Media, PDFs, and binary files.
- `99_Archive/` - Deprecated notes.

## 3. Metadata Standard (Frontmatter)
Every issue/story MUST have the following YAML frontmatter:

```yaml
---
id: STORY-001          # Unique ID (Prefix-Number)
type: story            # epic | story | bug | task
status: Backlog        # Backlog | To Do | In Progress | Review | Done
priority: Medium       # Low | Medium | High | Critical
assignee: "@human"     # @human | @ai-dev
created: 2026-04-23
due: 2026-05-01
epic: "[[EPIC-001]]"   # Optional link to parent epic
tags: [frontend, api]  # Subject tags
---
```

## 4. Visual Dashboard (Canvas)
The `DASHBOARD.canvas` should contain:
- **Kanban Flow:** Visual representation of `10_Issues/`.
- **Key Metrics:** Dataview queries showing open bugs and blocking tasks.
- **Architecture Overview:** High-level diagrams linked to `20_Specs/`.

## 5. Sync Protocol
- **Git Plugin:** The Obsidian Git plugin MUST be configured to auto-pull/push every 5 minutes or on file change.
- **GitHub Bridge:** Use `gh-to-md.py` (see Tooling) to import/export issues from GitHub/GitLab.

## 6. Graph DB Integration
To prepare for Graph DB ingestion:
- Use consistent `[[]]` linking.
- Tag relations explicitly: `related-to:: [[STORY-002]]`, `blocks:: [[STORY-003]]`.
- Dataview fields (`key:: value`) are preferred for additional structured data.

## 7. Tooling Recommendations
- **Obsidian Plugins:**
  - `Dataview`: For dynamic reports.
  - `Kanban`: For visual issue management.
  - `Templater`: For issue/story templates.
  - `Obsidian Git`: For version control.
  - `Tasks`: For managing checkboxes across files.
- **External CLI:** `rvc-sync` (Draft tool) for bulk operations.
