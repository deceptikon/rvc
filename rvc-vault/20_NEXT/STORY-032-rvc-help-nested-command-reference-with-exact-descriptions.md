---
id: STORY-032
title: rvc help: nested command reference with exact descriptions
type: story
priority: P2
started: 2026-09-16
---

# STORY-032: rvc help: nested command reference with exact descriptions

## Context

There is no `help` command — only argparse's auto `--help`, which dumps the flat
subcommand list and leaves the nested grammar (`rvc issue list` vs
`rvc issue ⟨ID⟩ ⟨action⟩`) implicit. The command surface was surveyed and written
down first:

- `10_CONTEXT/specs/COMMANDS.md` — exact, concise command reference (source of truth).
- It lists six detected ambiguities/duplicates (get ≡ issue ⟨ID⟩; list ≡ issue list;
  overloaded first positional on `issue`; init vs project init; rescan vs
  doctor --fix; tree `create` action vs `rvc create`).

## Acceptance criteria

1. `rvc help` renders every command with the exact concise description from
   COMMANDS.md, in the nested shape: `rvc help`, `rvc issue help`,
   `rvc project help`, etc. — sub-help per command group.
2. Each commands' help lists its arguments/flags with defaults, one per line,
   matching COMMANDS.md.
3. The nested structure mirrors reality: `issue` exposes `list`, `get`
   (≡ issue ⟨ID⟩), and transition actions; `project` exposes `init`/`info`.
4. `rvc help` exits 0 and needs no vault (pure static text), so it works before
   `init` — consistency with `rvc --help` output wording.
5. Every ambiguity/duplicate noted in COMMANDS.md (Notes section) is either
   resolved or explicitly acknowledged in the help text of the affected commands.

## Definition of done

- `python3 rvc-cli.py help` and `rvc-cli.py issue help` (etc.) print sane,
  COMMANDS.md-consistent text
- No command still lacks a one-line exact description
- COMMANDS.md stays the source of truth — code help either derives from it or is
  diffed against it
