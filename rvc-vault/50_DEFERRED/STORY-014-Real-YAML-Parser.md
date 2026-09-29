---
id: STORY-014
type: story
priority: P2
assignee: "@ai-dev"
epic: "[[EPIC-002-Conductor-v0.2-Hardening]]"
created: 2026-06-28
tags: [issue, rvc, workflow]
title: Real-YAML-Parser
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-014
deferred: 2026-09-29
---

# STORY-014: Replace Ad-Hoc YAML Parser with Real YAML Library

## 2026-09-29 — DEFERRED: it would trade a load-bearing property for a parsing edge case

Zero dependencies is not an accident of this codebase; it is the product. The same decision appears
independently in three places: the test runner is stdlib-only "so it needs no pytest, no network, no
conductor"; `avatar` is stdlib-only so it runs from a post-commit hook; and the context engine
replaced an embedding stack with stdlib retrieval. `rvc` is the tool a vault runs on itself, with
no install step — `pyyaml` would mean `pip install` before `rvc create` works, in the one tool whose
pitch is zero friction.

**The bug class is real but narrow, and scoped to a file that is not on the hot path.** The
ad-hoc parser lives in `vault-restructure.py` (mode `0600`, a legacy normalizer). The failure modes
listed — multiline `|`/`>` values, colons inside values, nested maps — are all things this vault's
*generated* frontmatter does not contain: it is a flat set of scalars and simple lists written by
`cmd_create_issue`, which the CLI itself round-trips.

**Re-entry condition.** Only if a real issue file is ever minted whose frontmatter cannot be parsed
— and then the fix is a *tolerant hand-rolled* extension, not a dependency, because the alternative
costs more than the bug. Add it if a vault ever needs frontmatter that exceeds what a flat reader
handles; do not add it to be correct in the abstract.

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
