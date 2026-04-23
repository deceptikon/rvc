---
id: STORY-001
type: story
status: To Do
priority: High
assignee: "@ai-dev"
created: 2026-04-23
---
# STORY-001: Issue Lifecycle Automation (The Status Shifter)

## Description
Current `rvc` tool only reads context. We need it to manage the lifecycle.
Add `rvc move <ID> <STATUS>` command that:
1. Finds the file by ID.
2. Updates the `status` field in YAML frontmatter.
3. Physically moves the file to the corresponding folder (e.g., `In Progress` -> `02_Active`, `Done` -> `04_Done`).
4. (Optional) Auto-commit the change to git.
