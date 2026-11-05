---
id: BUG-08
title: --skip-ci flag name inverts its effect — it disables the [skip ci] stamp
type: bug
priority: P2
started: 2026-11-06
---

# BUG-08: --skip-ci flag name inverts its effect — it disables the [skip ci] stamp

From FEEDBACK-rvc (ADLAI, 2026-11-05): `--skip-ci` on `create` and issue transitions DISABLES the `[skip ci]` stamp ("disable [skip ci] in the commit message (default: enabled)") — the name reads as "make this commit skip CI", which is the opposite of what it does. Someone wanting a quiet vault commit who passes `--skip-ci` will mint a full pipeline instead. Rename (e.g. `--no-skip-ci` or `--ci`) or make the help line lead with the inversion.
