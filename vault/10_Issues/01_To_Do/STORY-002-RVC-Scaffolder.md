---
id: STORY-002
type: story
status: To Do
priority: High
assignee: "@ai-dev"
created: 2026-04-23
---
# STORY-002: RVC Scaffolder (Zero-Friction Deployment)

## Description
To avoid manual setup, we need a one-command initializer: `rvc init <PROJECT_PATH>`.
It should:
1. Create the standard `vault/` directory structure.
2. Initialize a project-specific `REGLAMENT.md` in `00_Project/`.
3. Auto-generate the `.cursorrules` in the project root.
4. (Optional) Run `rvc-sync.py` to pull existing GitHub issues if git remotes are present.
