---
id: BUG-04
title: create --type bug|epic ignores type when minting the id prefix
type: bug
priority: P2
started: 2026-09-29
---

# BUG-04: create --type bug|epic ignores type when minting the id prefix

Repro: rvc create "x" --type bug mints STORY-<n>, not BUG-<n> (same with --type epic -> EPIC-<n>, seen 2026-09-29 minting the Avatar epic; had to git mv at birth). Filename/type frontmatter follow --type, only the prefix doesn't.

## Fix (2026-09-29)

Two parts:

1. **Prefix follows type.** `--prefix` now defaults to None; `cmd_create_issue` derives `bug→BUG`, `epic→EPIC`, else `STORY` when the caller did not pin one. Explicit `--prefix` still wins. (This issue itself was the repro: minted STORY-040 as `--type bug`, renamed to BUG-04 at birth.)
2. **Freed numbers are never reused.** Every mint raises a per-prefix high-water mark (`mint.<PREFIX>=<n>`) in the marker file — the tool's own memory, same pattern as `feedback.to=`. `_next_id` takes max(max-on-disk, floor); padding width follows any on-disk match so a floor above disk never narrows the format. The earlier same-day incident: STORY-040 minted, renamed to EPIC-004, then STORY-040 minted *again* for a different issue — impossible now.

Contract note: `test_feedback_self_ingest_does_not_self_configure` refined — self-ingest may write `mint.*` (id memory) but never `feedback.*`/`plate.*` for itself.
