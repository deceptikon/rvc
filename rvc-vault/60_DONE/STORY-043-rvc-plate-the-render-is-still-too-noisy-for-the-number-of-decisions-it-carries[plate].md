---
id: STORY-043
title: rvc plate: the render is still too noisy for the number of decisions it carries
type: story
priority: P2
domain_tags: [plate, rvc]
started: 2026-11-06
---

# STORY-043: rvc plate: the render is still too noisy for the number of decisions it carries

## Problem

The DOMAINS block was cut from a tag dump to a four-line histogram, and the same reading should now be
applied to the whole render. Observed on this vault (10 live surfaces) and on ADLAI's (25 surfaces,
read-only): file names repeat across lanes, each row is its own line, and the plate length grows with
the tree instead of with the decisions in it.

## Open questions (discussion, not a spec)

1. Rows by **id** rather than filename — the lanes already imply the bucket, and the filename carries a
   title nobody re-reads on the plate.
2. One **folded** shape for the empty lanes: seven headers with a `—` is five lines of nothing.
3. Should RECENT ACTIVITY be a separate command (`rvc log`) so the plate stays a state view and the
   log stays a history view?
4. What is the plate *for* in one sentence — the answer decides what may be cut.

Deliberately left out of BUG-14: that letter was about domain_tags, and its fix is in.
