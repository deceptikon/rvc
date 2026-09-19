---
id: STORY-038
title: RVC root adopts the new-layout marker (single .rvc-root at project root)
type: story
priority: P2
started: 2026-09-19
---

# STORY-038: RVC root adopts the new-layout marker (single .rvc-root at project root)

## Incident
A stray `rvc init` at the RVC repo root minted a second vault (0-vault) and repointed AGENTS/CLAUDE/GEMINI/QWEN at it — the constitution stopped loading. Root cause: cmd_init didn't detect the legacy inner self-ref vault (rvc-vault/.rvc-root, vault=rvc-vault).

## Resolution (marker relocation — data never moved)
- git mv rvc-vault/.rvc-root -> RVC/.rvc-root (vault=rvc-vault name preserved). Repo now matches STORY-037: named vault subdir + single marker at project root. Resolution from root/inside vault/subprojects unchanged.
- Deleted the empty 0-vault; restored the 4 symlinks to rvc-vault/10_CONTEXT/ROUTING.md.
- cmd_init now refuses to scaffold a second vault when a child owns an inner .rvc-root (+ test).
- Context benchmark scratch copies carry the effective marker (marker_file) — markerless copies fell back to LEGACY_TREE and graded recall against the wrong bucket map.

## AC
- [x] RVC root resolution -> rvc-vault from root, rvc-vault/, and subdirs
- [x] constitution loads again (symlinks restored)
- [x] cmd_init refuses second vault when inner marker exists (test_init_refuses_second_vault_when_inner_vault_exists)
- [x] suite 109 passed / 0 failed / 1 skipped (benchmark recall restored 80%+)
