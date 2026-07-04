---
id: STORY-007
type: story
status: Done
priority: P1
assignee: "@ai-dev"
epic: "[[EPIC-001-RVC-Protocol]]"
created: 2026-04-23
title: Git-Sync-Automation
tags: [issue, workflow]
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-007
---

# STORY-007: Bulletproof Git-Sync & State Locking

## Description
To prevent the "Git Conflict Nightmare" between Obsidian humans (auto-saving) and CLI agents (auto-moving files), we need strict state-locking and sync rules.

### Requirements:
1. **Obsidian Side**: Configure 'Obsidian Git' plugin to pull every 3 mins, and commit/push on file change.
2. **CLI/Agent Side**: Any `rvc issue <ID> [state]` command MUST execute a `git pull --rebase` BEFORE modifying the file, and a `git commit && git push` IMMEDIATELY AFTER.
3. **Conflict Fallback**: If a standard merge fails during an agent command, favor the remote (usually human) or append the agent's proposed state change as a comment at the bottom of the file.