# RVC Vault — Routing (the constitution)

This is the root document for `rvc-vault` — the RVC repo's own dogfooding vault
(**newvault** tree). Folder = state: where an issue file sits *is* its status.

## Lifecycle buckets

| Bucket | Meaning | Arrive via |
|--------|---------|-----------|
| `00_INBOX` | raw ideas, unrefined | `rvc issue create` |
| `20_NEXT` | triaged, ready to pick up | `triage` |
| `30_ACTIVE` | in progress | `start` |
| `40_DECIDE` | blocked on a decision | `block` |
| `50_DEFERRED` | parked | `defer` |
| `60_DONE` | completed, kept visible | `review` / `done` |
| `90_ARCHIVE/done` | evicted after done | `evict` |
| `90_ARCHIVE/superseded` | replaced by another issue | `supersede` |

## Transitions

```bash
rvc issue <ID> start|triage|block|defer|review|done|evict|supersede
```

All transitions are a plain `git mv` (+ optional commit). The CLI never reads or writes
frontmatter `status:` — folder is the single source of truth. The `.rvc-root`
`tree.<verb>=<dir>` block is the Dev-on-map for this vault.

## Session protocol

1. **Open:** clarify the goal; load the active issue's context (`rvc context <ID>`).
2. **Work:** keep `30_ACTIVE/` to one in-flight issue; move it to `40_DECIDE`/`50_DEFERRED`
   when blocked instead of leaving it rot in place.
3. **Close:** land the work, un-xfail/mark tests, commit, then `rvc issue <ID> done`.
4. **Log:** append architectural decisions and traps to `10_CONTEXT/DECISIONS.md` /
   `10_CONTEXT/GOTCHAS.md` (append + prune, never append-only).
5. Update `10_CONTEXT/STATE.json` on open/close.

## Rules of the vault

- Never edit `status:` frontmatter — the folder owns state.
- Protocols & specs live in `10_CONTEXT/specs/` — `PROTOCOL.md` (this project's protocol),
  `REGLAMENT.md` (rules), `AGENTS.md` (agent guide), `HANDOVER.md` (handover template).
- Bare `rvc` on PATH is the folder-as-state CLI (symlinked to `rvc-cli.py`) — if `~/.local/bin`
  ever loses the link, re-run `python3 rvc-cli.py install`.