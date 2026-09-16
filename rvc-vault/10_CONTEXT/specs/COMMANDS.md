# COMMANDS — RVC CLI Reference

Single source of truth for the `rvc` command surface. Every command listed here is
described exactly and concisely, nested by structure. Written before any `help`
feature, so ambiguity and duplication can be caught before they are enshrined in
help text.

Legend: `⟨required⟩` · `[optional]` · `--flag VALUE` · `(default)`

---

## Global

```
rvc --path ⟨path⟩ ⟨command⟩ …
```
- `--path` — project or vault path to operate on (default `.`). `rvc-cli.py` finds
  the vault by walking up 8 levels from there, `.rvc-root` marker first.

---

## Top-level commands

### `rvc init`

```
rvc init [⟨dir⟩] [--tree legacy|newvault]
```
Initialize a new flat vault (no `vault/` subdirectory) at `⟨dir⟩` (default `.`).
`--tree` selects the bucket layout preset (default `legacy`).

### `rvc project`

```
rvc project init [⟨dir⟩] [--vault-name ⟨name⟩] [--tree legacy|newvault]
rvc project info [⟨dir⟩]
```
- `project init` — initialize a project with a `⟨vault-name⟩/` subdirectory (default
  `vault`) and the chosen tree preset.
- `project info` — print vault info and the contents of `ROADMAP.md` if present.

### `rvc install`

```
rvc install [--dir ⟨dir⟩] [--force] [--check]
```
Install this script as `rvc` on PATH (symlink → `⟨dir⟩/rvc`, default
`~/.local/bin`). `--force` overwrites an unrelated existing file; `--check` verifies
installation and exits without changes.

### `rvc create`

```
rvc create ⟨title⟩ [--prefix ⟨PREFIX⟩] [--type story|bug|task|epic]
             [--priority P0|P1|P2|P3|Low|Medium|High|Critical]
             [--body ⟨text⟩] [--dir ⟨bucket⟩] [--epic ⟨EPIC-XX⟩] [--skip-ci]
```
Create a new issue. Mints the next ID (`⟨PREFIX⟩-NN`, default `STORY`), writes
frontmatter (`id`, `title`, `type`, `priority`, `started`), and lands in the
vault's `create` bucket (default `00_INBOX` on newvault trees). On a tree that
declares a `block` bucket, legacy priorities translate to P0-P3 and a `status:`
field is refused (folder owns state). Commits with `[skip ci]` unless `--skip-ci`
is disabled.

### `rvc issue`

```
rvc issue list [⟨status|bucket⟩] [--dir ⟨bucket⟩]
rvc issue ⟨ID⟩
rvc issue ⟨ID⟩ ⟨action⟩ [--skip-ci]
```
- `issue list` — list issues; optional positional filters by status alias or bucket,
  `--dir` lists a specific configured bucket.
- `issue ⟨ID⟩` — print the issue file (alias of `rvc get`).
- `issue ⟨ID⟩ ⟨action⟩` — transition the issue through the vault's tree
  (`triage`, `start`, `block`, `defer`, `review`, `done`, `evict`, `supersede`,
  plus `create`); the valid set comes from the vault's own `.rvc-root`
  `tree.<verb>=<dir>` lines. A plain `git mv` + commit.

### `rvc get`

```
rvc get ⟨ID⟩
```
Print the raw issue file for `⟨ID⟩`.

### `rvc context`

```
rvc context ⟨ID⟩
```
Assemble linked context: read the issue, resolve every `[[wikilink]]` in its body
against the vault index, and print each referenced file in full.

### `rvc list`

```
rvc list [⟨status⟩] [--dir ⟨bucket⟩]
```
Alias for `rvc issue list`.

### `rvc search`

```
rvc search ⟨query⟩
```
Case-insensitive grep over every `.md` file in the vault; prints
`path:line: content` for matches.

### `rvc plate`

```
rvc plate [--as ⟨handle⟩] [--format text|json] [--stale-days ⟨N⟩]
```
Render the plate: lanes computed from folders, priorities and open asks
(`next`, `active`, `waiting`, `overdue`, `inbox`, `owes_turn`, `owner`).
`--as` canonicalizes a handle for the owed-turn lane; without it the render is
identity-free. `--format json` emits a machine-readable payload. `--stale-days` is
the overdue threshold (default 7).

### `rvc doctor`

```
rvc doctor [--fix]
```
Audit the vault against its own constitution. On a tree that declares a `block`
bucket: `status:` fields in live buckets are violations, off-vocabulary
`priority:` is a warning. `--fix` strips `status:` and folds priorities
(`High`→`P1`, `P0.0.0`→`P0`) in place. Archives are never touched; legacy trees
(no `block` bucket) are exempt.

### `rvc rescan`

```
rvc rescan [--dry-run]
```
Fix frontmatter, add wikilinks, infer tags across the vault (delegates to
`vault-restructure.py`). On block-bucket trees the normalizer strips `status:`
instead of normalizing it. `--dry-run` shows changes without writing.

### `rvc git-commit-all`

```
rvc git-commit-all ⟨message⟩ [--dry-run] [--no-push] [--push]
```
Commit across all dirty submodules plus the parent repo (safe incremental).
`--push` opts into pushing (push is otherwise disabled); `--no-push` overrides it.

---

## Notes on ambiguity & duplication (detected while writing this doc)

1. **`rvc issue ⟨ID⟩` ≡ `rvc get ⟨ID⟩`** — one fetcher spelled two ways, and
   `issue ⟨ID⟩`'s hint block advertises `rvc context` but not `rvc get`. Keep both
   or merge; decide once.
2. **`rvc list` duplicates `rvc issue list`** — the alias is welcome for muscle
   memory, but help must surface both so users do not think they are different.
3. **`issue ⟨ID⟩ ⟨action⟩` vs `issue list`** — the first positional is
   overloaded: `list` is a subcommand, anything else is read as an ID. Help text
   must state this explicitly; it is the single most confusing parse in the CLI.
4. **`project init` vs `init`** — `init` makes a flat vault, `project init` makes
   a project with a vault subdirectory. Both take `--tree`; one takes
   `--vault-name`. Keep the split, but the one-line help must not say "initialize"
   for both without the distinction.
5. **`rescan` vs `doctor --fix` overlap** — both rewrite frontmatter on
   block-bucket trees. `doctor --fix` is surgical (status/priority only), `rescan`
   is broad (tag/wikilink normalization). Help must call out the difference to
   prevent `rescan` from being the default "clean my vault" reflex.
6. **Tree actions include `create`** — `rvc issue ⟨ID⟩ create` is a valid
   transition on trees that declare a `create` bucket. This collides conceptually
   with `rvc create ⟨title⟩`. Harmless today (different positional shapes), but the
   transition list help should not claim "lifecycle verbs only".
7. **Minted frontmatter says `started:` where vault files say `created:`** — the
   `create` command writes `started: ⟨today⟩`; existing vault stories carry
   `created:`. Same concept, two field names. The help/reference must not imply
   they are interchangeable, and a single canonical name should be picked.