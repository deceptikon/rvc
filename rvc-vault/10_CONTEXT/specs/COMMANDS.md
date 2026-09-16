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
- `issue ⟨ID⟩` — hidden alias of `rvc get` (kept working, never advertised in help).
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

Resolutions were decided at STORY-032 triage; the help implementation must match
them, not re-litigate them.

1. **`rvc get ⟨ID⟩` is the primary viewer; `rvc issue ⟨ID⟩` is a hidden alias.**
   The `issue` first positional cannot carry three grammars (`list` subcommand, ID
   viewer, ID+action transition) in help. `issue` help says "view: `rvc get ⟨ID⟩`";
   the alias keeps working but is never advertised.
2. **`rvc list` stays an alias of `rvc issue list`.** Both help texts say so.
3. **`issue ⟨ID⟩ ⟨action⟩` vs `issue list`** — the overloaded first positional is
   resolved by rule 1: only `list` and ID+action remain, and help states the parse
   explicitly.
4. **`project init` vs `init`** — both keep. `init` makes a flat vault; `project
   init` makes a project with a vault subdirectory. Help distinguishes them
   explicitly instead of saying "initialize" for both.
5. **`rescan` vs `doctor --fix`** — both keep; distinct scope. `doctor --fix` is
   surgical (status/priority only, constitution repair), `rescan` is broad
   (tag/wikilink/frontmatter normalization). Help warns `rescan` is the broader
   rewrite so it is not the default "clean my vault" reflex.
6. **Tree actions include `create`** (`rvc issue ⟨ID⟩ create`) — emergent property
   of the tree-verb model, not a CLI duplicate. Acknowledged in transition help;
   not removed.
7. **Minted frontmatter says `started:` where vault files say `created:`** — same
   concept, two field names. Help/reference must not imply they are
   interchangeable; a single canonical name should be picked (pending decision).