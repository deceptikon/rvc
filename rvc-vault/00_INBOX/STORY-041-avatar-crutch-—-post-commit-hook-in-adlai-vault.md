---
id: STORY-041
title: avatar crutch — post-commit hook in adlai-vault
type: story
priority: P1
epic: [[EPIC-004]]
started: 2026-09-29
---

# STORY-041: avatar crutch — post-commit hook in adlai-vault

Thin wiring, v0 already fired live once. A post-commit hook in adlai-vault calls `avatar notify` after every commit — the vault itself asks the bot to ping NEW owed turns. No daemon, no cron habit; dedupe state keeps it silent when nothing changed. Event-driven fits folder-as-state: a transition IS a commit.
