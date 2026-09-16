---
id: STORY-028
type: bug
priority: P2
created: 2026-09-16
domain: workflow_meta
domain_tags: ["rvc", "frontmatter", "portability"]
---

# STORY-028: `rvc create` mints issues with no `id:` field, so they cannot be relinked

---

## Reproduced (2026-09-16, this session)

Scratch vault with `tree.create=00_INBOX`, then:

```
$ rvc --path <v> create "probe" --priority High
[RVC] priority 'High' -> 'P1' (this tree sorts P0-P3)
[RVC] Created STORY-01-probe.md
```

Landed in `00_INBOX` ✅ and the priority translation is correct ✅. But the minted frontmatter is:

```yaml
type: story
priority: P1
started: 2026-09-16
```

No `id:`, no `title:`. **The filename is the only carrier of the issue's identity.**

## Why it matters

This is not cosmetic. Three of ADLAI's live tickets (`STORY-107`, `STORY-108`, `STORY-109`) were
CLI-minted and carry no `id:` field. The moment a vault move needs to rewrite wikilinks pointing at
them, there is nothing machine-readable to key on — only a filename that itself encodes the id in a
format that varies with padding (`STORY-01` minted above versus this vault's `STORY-019`, and
ADLAI's `STORY-109`). Two vaults, two paddings, and the id field that would reconcile them does not
exist.

The `rescan` verb normalizes frontmatter, which implies the contract is that `id:` should be present
— `create` just never writes it.

## Acceptance criteria

1. `cmd_create` writes `id:` and `title:` into minted frontmatter.
2. ID padding is derived from the vault's existing high-water mark and is stable, so a vault does not
   produce `STORY-09` next to `STORY-010`.
3. A ticket moved between vaults can be relinked by reading frontmatter alone.
4. Regression test asserting the minted file contains `id:` — this is the test that would have caught
   the drift below.

## Related, not the same bug

ADLAI `STORY-107` reported on 2026-09-13 that `rvc create` ignored `tree.create` and landed issues in
`20_NEXT`. **That does not reproduce today** — re-verified above, and `rvc-cli.py:637` reads
`tree.get("create") or tree["triage"]`. It was fixed the next day by **`42aefb6` "fix: create lands in
tree.create bucket; push is opt-in (RVC_PUSH) (STORY-105)"**, and nobody closed the finding. Three
days on, the only way to learn it was fixed was to re-run the experiment. See STORY-030 for why that
happened.
