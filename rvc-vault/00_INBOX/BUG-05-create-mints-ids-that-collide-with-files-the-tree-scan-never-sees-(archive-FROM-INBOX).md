---
id: BUG-05
title: create mints ids that collide with files the tree scan never sees (archive FROM INBOX)
type: bug
priority: P2
started: 2026-11-06
---

# BUG-05: create mints ids that collide with files the tree scan never sees (archive FROM INBOX)

From FEEDBACK-rvc (ADLAI, 2026-11-05): `rvc create` minted STORY-153 while STORY-153 already existed in `90_ARCHIVE/FROM INBOX/` — the max-on-disk ID scan does not cover the archive subfolders the tree never names, so newly minted ids can collide with archived ones (ids are supposed to be permanent). Scan every bucket for the max id, or refuse to mint an id that already exists anywhere on disk.
