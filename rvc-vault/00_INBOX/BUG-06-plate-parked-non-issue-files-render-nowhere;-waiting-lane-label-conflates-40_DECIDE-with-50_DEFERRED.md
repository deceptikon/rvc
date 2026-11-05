---
id: BUG-06
title: plate: parked non-issue files render nowhere; waiting lane label conflates 40_DECIDE with 50_DEFERRED
type: bug
priority: P2
started: 2026-11-06
---

# BUG-06: plate: parked non-issue files render nowhere; waiting lane label conflates 40_DECIDE with 50_DEFERRED

From FEEDBACK-rvc (ADLAI, 2026-11-05): `50_DEFERRED/` items appear on NO plate lane. Measured: `50_DEFERRED/ESSAY--The-Pilot-and-the-Prison-Guard.md` exists but renders nowhere — the plate showed "WAITING — deferred on purpose [0]" with the essay parked; after blocking STORY-157, that same lane renders the `40_DECIDE/` item instead. The lane labelled "deferred on purpose" actually shows blocked-on-ruling items, while the bucket that IS deferred on purpose is invisible (non-issue files fail the is_issue gate). Render every parked file (fold into WAITING with a bucket tag) and relabel the lane so rulings and parks read apart.
