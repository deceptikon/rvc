# Feedback to RVC — client protocol (for rvc-viewed projects)

Found a bug or friction in RVC tooling? File it in one command. No vault-to-vault
letter-dropping, no config editing, no remembered dance — the report becomes a real
`BUG-<n>` in RVC's vault and shows up on *your* plate until it's fixed.

## 1. Write the report

Drop a dated letter in your inbox (`00_INBOX/FEEDBACK-rvc.md`, or any path):

```markdown
# FEEDBACK-rvc

- **2026-09-19:** <what broke / what confused you — steps to reproduce>
```

One file = one report.

## 2. Send it

```bash
rvc feedback @00_INBOX/FEEDBACK-rvc.md
```

That's it. No setup — the command handles everything itself:

- the letter becomes `BUG-<n>` in RVC's vault (`origin: <your project>` in frontmatter),
- the source file is removed (and committed as a handoff),
- your vault's `.rvc-root` gets its feedback lane configured for you on first use
  (`feedback.to=`, `plate.source.rvc=`, `plate.alias.rvc=F`),
- it prints your dashboard line:

```text
RVC BUGS — pending: BUG-14 | done: 0 of 1
```

> `--no-remove` keeps the source letter; `--to <path>` targets a different vault than
> the auto-discovered one. Your own handwritten `.rvc-root` lines still win over the
> auto-written ones.

## 3. Watch it

Your plate gains a derived lane (IDs and counts only — nothing else crosses):

```text
EXTERNAL FEEDBACK — derived from other vaults (IDs and counts only)
  rvc: pending: F-14 | done: 0 of 2
```

- **`F-<n>` is *your* feedback** — an alias of RVC's `BUG-<n>` so you can tell it apart
  from your own issues at a glance. The record in RVC stays `BUG-14`.
- An item flips to `done` when RVC lands the fix.