---
id: STORY-029
type: task
priority: P3
created: 2026-09-16
domain: workflow_meta
domain_tags: ["rvc-vault", "hygiene", "drift"]
---

# STORY-029: This vault violates its own constitution 26 times

---

`ROUTING.md` here says it twice — "The CLI never reads or writes frontmatter `status:` — folder is the
single source of truth" and "Never edit `status:` frontmatter — the folder owns state."

- **26 files** in `20_NEXT/` and `60_DONE/` carry a `status:` field.
- `priority:` vocabulary in use is `High` ×10, `P0` ×4, `P1` ×6, `P2` ×4, `P3` ×1 — and one
  **`P0.0.0`**, which is neither vocabulary and sorts nowhere.

This is filed at P3 on purpose and it is filed here rather than in a rush. The reason to write it down
now is the honest one: **ADLAI is spending a full architectural milestone compiling exactly this
disease out of its own constitution, and this vault has a worse case of it.** Two independent vaults
growing the same rot is evidence the failure is in the protocol's tooling and onboarding, not in
either team's discipline — which is a better argument for RVC owning the guard than anything ADLAI
could file against itself.

## Acceptance criteria

1. Every `status:` field stripped from live files in this vault (archive may keep what it was filed
   with).
2. Priority vocabulary normalized to `P0`–`P3`; the `P0.0.0` strays folded.
3. **The structural fix, which is the point of the story:** `rvc rescan` or a `rvc doctor` check
   *refuses* to mint or keep a `status:` field on a tree that declares a `block` bucket, and warns on
   off-vocabulary `priority:`. ADLAI's `LEGACY_PRIORITY_TO_P` translation at `rvc-cli.py:632` already
   proves the tool can detect this — it just only does so at creation, not on audit.
4. A guard at mint time beats a compile every three months. Prefer criterion 3 over criterion 1 if
   only one gets done; the cleanup is worthless without it, because the same drift will regrow.
