---
id: BUG-04
title: create --type bug|epic ignores type when minting the id prefix
type: bug
priority: P2
started: 2026-09-29
---

# BUG-04: create --type bug|epic ignores type when minting the id prefix

Repro: rvc create "x" --type bug mints STORY-<n>, not BUG-<n> (same with --type epic -> EPIC-<n>, seen 2026-09-29 minting the Avatar epic; had to git mv at birth). Filename/type frontmatter follow --type, only the prefix doesn't.
