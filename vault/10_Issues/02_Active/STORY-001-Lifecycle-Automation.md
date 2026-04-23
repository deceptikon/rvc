---
id: STORY-001
type: story
status: Active
priority: High
assignee: "@ai-dev"
epic: "[[EPIC-001]]"
created: 2026-04-23
---
# STORY-001: RVC CLI Tree & Minimal State Machine

## Description
Refactor the `rvc-cli.py` to use a deterministic, tree-style command structure. We must keep statuses minimal to avoid human/AI confusion and map them strictly to the folder structure.

### CLI Specification:
- `rvc issue <ID>`: Default read. Gets the issue.
- `rvc issue <ID> start`: Moves file to `02_Active`, updates status to `Active`.
- `rvc issue <ID> review`: Moves file to `03_Review`, updates status to `Review`.
- `rvc issue <ID> done`: Moves file to `04_Done`, updates status to `Done`.
- `rvc issue list [inbox|active|review|done]`: Filters and lists issues.
- `rvc issue create`: Triggers an interactive prompt for new issues.
- `rvc project init <PATH>`: Scaffolder integration.
- `rvc project info`: Reads ROADMAP.md and stats.

### Constraint
Eliminate free-text statuses. The state machine is strictly: Inbox -> Active -> Review -> Done.