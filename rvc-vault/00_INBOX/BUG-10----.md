---
id: BUG-10
title: ---
type: bug
priority: P2
origin: adlai-vault
submitted: 2026-11-06
---

# BUG-10: ---

---
type: feedback
tool: rvc
source: STORY-128 / STORY-141
date: 2026-09-27
---

# FEEDBACK — `rvc plate` AC counters read 0/0 for any story with numbered acceptance criteria

**Symptom.** The ACTIVE lane renders every ADLAI story as `open=0 done=0`, including stories whose
ACs are visibly checked:

```
ACTIVE (WIP cap 2)  [1]
  STORY-141-Citations-are-statute-blind-…  open=0 done=0
```

`STORY-128` showed `open=0 done=0` all session while carrying 6 checked and 2 unchecked criteria.

**Cause** (`TEAMFLOW/RVC/rvc/plate.py:149-150`) — the counters match dash bullets only:

```python
"open_boxes":  len(re.findall(r"^\s*-\s*\[ \]", text, re.M)),
"done_boxes":  len(re.findall(r"^\s*-\s*\[[xX]\]", text, re.M)),
```

Numbered criteria (`1. [ ]`, `2. [x]`) never match, so they count as neither open nor done.

**Scope, measured on this vault just now** (`STORY-*.md` files containing at least one box):
110 files use the dash form, 18 use the numbered form. The convention is genuinely mixed — and the
numbered form is what the two P0 stories worked this session use, which is why the counter looked
like it was reporting "no ACs tracked" on the hottest items on the plate.

**Why it matters here.** The constitution forbids a `status:` field anywhere — "the folder *is* the
state" — so the per-story AC box count is the only progress signal `plate` can carry. A lane that
renders `0/0` reads as "nothing tracked" and is indistinguishable from "not started", which is
exactly the blind spot `plate` exists to close.

**Two ways out — TEAMFLOW's call, not mine:**

1. Widen the regex to both list markers, e.g. `^\s*(?:[-*]|\d+\.)\s*\[[xX]\]`. One line, no vault
   churn, keeps the mixed convention tolerated.
2. Declare dash bullets the only sanctioned AC form and normalise the 18 numbered files at
   `rvc rescan`. Keeps one grammar, costs a vault-wide rewrite.

Recommendation: **(1)** — it is one regex, and option (2) edits 18 files to satisfy a renderer
rather than a rule anyone is being harmed by.

**Minor, same file:** if the counter is left as-is, rendering `open=? done=?` (or omitting the
pair) when a story has zero *recognised* boxes but does contain `[ ]`/`[x]` anywhere would at least
distinguish "no ACs" from "ACs in a grammar I can't read". Silent `0/0` is the worst of the three
outcomes because it looks like data.

**Addendum 2026-09-28:** STORY-122 is a third affected P0 — two open work items (numbered `5.`/`6.`,
plus a numbered AC and one `- [ ]` bullet) render as `open=1 done=7`, understating the story by two
thirds while it sits in a WIP-cap-2 lane.

