---
id: BUG-07
title: search: multi-word queries have no fallback and No results does not say why
type: bug
priority: P2
started: 2026-11-06
---

# BUG-07: search: multi-word queries have no fallback and No results does not say why

From FEEDBACK-rvc (ADLAI, 2026-11-05): multi-word queries behave as an exact-token AND with no stemming or substring fallback, and "No results" does not say why — `rvc search "apostrophe filename"` returned nothing (the file says "filenames", not "filename") while `rvc search "apostrophe"` returned 3 matches a second earlier on the same cache. Suggest stemming/substring fallback, or at least a hint to retry with fewer words.
