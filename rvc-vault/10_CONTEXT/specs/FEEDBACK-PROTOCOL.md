# Feedback to RVC — client protocol (for rvc-viewed projects)

Found a bug or friction in RVC tooling? File it in one command. No vault-to-vault
letter-dropping, no remembered dance — the report becomes a real `BUG-<n>` in RVC's
vault and shows up on *your* plate until it's fixed.

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

That's it. The letter becomes `BUG-<n>` in RVC's vault (`origin: <your project>` in
frontmatter), the source file is removed, and the command prints your dashboard line:

```text
RVC BUGS — pending: BUG-14 | done: 0 of 1
```

> `--no-remove` keeps the source letter; `--to <path>` overrides the configured target.

## 3. Watch it

Your plate gains a derived lane (IDs and counts only — nothing else crosses):

```text
EXTERNAL FEEDBACK — derived from other vaults (IDs and counts only)
  rvc: pending: F-14 | done: 0 of 2
```

- **`F-<n>` is *your* feedback** — an alias of RVC's `BUG-<n>` so you can tell it apart
  from your own issues at a glance. The record in RVC stays `BUG-14`.
- An item flips to `done` when RVC lands the fix.

## Setup (once)

Append to your vault's `.rvc-root`:

```
feedback.to=<path-to-RVC-vault>
plate.source.rvc=<path-to-RVC-vault>
plate.alias.rvc=F
```

- `feedback.to` — target for `rvc feedback` when you don't pass `--to`.
- `plate.source.rvc` — where your plate reads RVC's tree from.
- `plate.alias.rvc` — the one-letter provenance alias (here `F`).