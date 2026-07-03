---
id: STORY-014
type: story
status: To Do
priority: P2
assignee: "@ai-dev"
epic: "[[EPIC-001]]"
created: 2026-06-28
tags: [issue, rvc, workflow]
title: Real-YAML-Parser
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-014
---

# STORY-014: Replace Ad-Hoc YAML Parser with Real YAML Library

## Context
`vault-restructure.py` implements `parse_frontmatter()` via manual string splitting on `:`. This breaks on multiline values, values containing colons, quoted strings with nested quotes, and list values.

## Acceptance Criteria
- [ ] Add `pyyaml` or `ruamel.yaml` to `pyproject.toml` dependencies.
- [ ] Replace `parse_frontmatter()` with proper YAML loading via `yaml.safe_load()`.
- [ ] Replace `fm_to_yaml()` with `yaml.dump()` or `ruamel.yaml` round-trip parser.
- [ ] Ensure idempotency: running rescan on already-normalized files produces zero changes.
- [ ] Handle edge cases: multiline strings (`|` or `>`), lists (`tags: [a, b]`), nested maps.

## Test Case
Create a file with complex frontmatter:
```yaml
---
type: story
description: |
  This is a multiline
  description with: colons
tags: [retrieval, llm, "special:tag"]
---
```
Run `rvc rescan` twice. Assert zero changes on second run.
