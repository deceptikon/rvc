---
id: BUG-14
title: FEEDBACK-rvc — deposit from ADLAI (STORY-162)
type: bug
priority: P2
origin: adlai-vault
submitted: 2026-11-06
domain_tags: [rvc, plate, feedback]
---

# BUG-14: FEEDBACK-rvc — deposit from ADLAI (STORY-162)

---
type: feedback
title: rvc feedback — make domain_tags real (filename, create flag, doctor rule, context line)
created: 2026-11-06
---

# FEEDBACK-rvc — deposit from ADLAI (STORY-162)

`domain_tags:` is already load-bearing in this vault (~130 archived issues, plus `DECISIONS.md` /
`GOTCHAS.md`), and `rvc context` already ranks it (`context.py:44` `CONTEXT_TAG_KEYS`, weight 2.5).
Nothing else in the toolchain supports it, so the tag decayed. Four asks, in order of value:

1. **Put the domain in the filename.** This is the one that actually fixes visibility: a listing, a tab
   title, `ls`, a grep hit and an Obsidian backlink all show the *name*, and none of them show frontmatter —
   so a tag that only lives in the header is invisible at exactly the moment a human is choosing which file
   to open. Suggested shape at create: `STORY-162[review_queue]-make-domain-tags-mean-something.md`,
   prefix order unchanged so the existing `STORY_FILE_RE` / id-first lookups keep resolving. Needs three
   things from rvc, because a name that can change is a different beast from a name that is born:
   - `rvc create --domain-tags ⟨slug⟩` stamps it once at mint time;
   - `rvc issue ⟨ID⟩ domain ⟨slug⟩` renames on a ruling (a `git mv`, like every other transition verb, with
     the same `[skip ci]` discipline), and rewrites `epic: [[…]]` wikilinks plus any `[[name]]` backlink
     that pointed at the old path — ADLAI links are filename-based (`[[EPIC-11-FE-Design-Handoff]]`), so a
     bare rename silently orphans them;
   - `rvc doctor` flags the mismatch between the filename slug and the frontmatter value, so the two cannot
     drift into the classic ADLAI failure: one fact, two places, disagreeing.
   - **Placement constraint (verified in the parsers):** id resolution anchors at the *start* of the stem —
     `rvc/core.py:735` (`^{prefix}-(\d+)`) and ADLAI's `scripts/vault_status.py:81`
     (`^(STORY|EPIC|Q)-\d+`) — so the slug has to sit **after** the id and before the title
     (`STORY-162[review_queue]-title.md`). Anywhere else, and `rvc get`, `rvc plate` and the census stop
     finding the issue.
   - Cost to weigh before building: the filename becomes a mutable field rather than an identity, and
     renames are history-breaking for anything that copied a path. If rvc would rather keep names immutable,
     the fallback is ask 4 below plus a create-time stamp only, and ADLAI accepts that the domain is
     discoverable by `rvc plate` grouping instead of by eye in `ls`.
2. **`rvc create --domain-tags ⟨slug⟩` regardless of the filename decision.** `cli/commands.py:153-164`
   exposes `--epic` but no tag flag, while `issues.py:166,222-229` already accepts `extra_frontmatter` —
   plumbed and unwired. Until create can set it, every new issue lands out of spec and any per-issue
   invariant is false by construction.
3. **A `doctor` vocabulary rule for the tag.** `doctor.py:17,62` already refuses `status:` and folds
   off-vocabulary `priority:`. The same shape fixes what rotted here: multi-valued lists (up to 4), the
   item's own type used as a tag (`"story"`, `"epic"`), and near-synonyms (`corpus`/`legal_corpus`,
   `citation`/`review_queue`, `infra`/`database`). ADLAI publishes its controlled 11-slug list in
   `10_CONTEXT/specs/Story-Domains.md`; doctor only needs a per-vault vocabulary file to read.
4. **One line in `rvc context`.** Section 1 prints `State | Priority | Type | File` and no tags, so a
   session must open the file to learn the domain it is already ranking on. Echo `domain_tags` there — and
   if it is in the filename, print the slug on its own line so `rvc plate` can group by domain.

Friction, not a blocker: the tag was settable by hand for a year and unsurfaced by tooling, so it silently
stopped meaning anything — the failure mode is a missing ritual with no mechanical teeth behind it, and a
fact stored where nobody looks.

---

## Field report from ADLAI's STORY-162 run (2026-11-06, first consumer)

Used `rvc set --domain` to tag all 28 live ADLAI issues. What worked: scalar write, filename stamping,
`[[…]]` wikilink healing on rename (verified: EPIC-11's three children followed their epic's rename),
`rvc get`/`context` id resolution intact, and the `**Domain:**` echo in the context header (ask 4). Three
observations for the follow-up:

1. **Ranking is unchanged by the tag.** For one `review_queue`, one `eval` and one `retrieval` issue,
   `rvc context` does not rank the matching `Story-Domains.md` section into the top matches (0 hits on
   all three) — the slugs enter the weights (`context.py:44,87-88`) but a vocabulary spec is thin against
   content-dense files. If domain-driven ranking is a goal, it needs a boost rule for the matching spec
   section, or the honest fallback: domain is discoverable by `rvc plate` grouping, not ranking.
2. **Titles with brackets get two groups.** `STORY-151-Own-the-huggingface-hub[cli]-…[runtime].md` — a
   pre-existing `[cli]` in the title plus the domain stamp. Start-anchored id resolution is unaffected,
   but a future `doctor` name-vs-header check must anchor on the **last** bracket group, not the first.
3. **`[[stem[slug]]]` wikilinks nest brackets.** Obsidian tolerates it; stricter markdown link-walkers
   may not. Noted in case the heal regex ever grows a validator.


---

## Realization review (2026-11-06, second pass)

The plate section of ask 4 rendered the tag field, not a domain view: grouping keyed on the raw
`domain_tags:` string, so a multi-tag issue was its own "domain" and every group enumerated full file
names — `["rvc", "protocol", "story"] (2): STORY-013-RVC-Security-Performance.md, …`. Replaced with a
histogram per slug (`protocol×7  rvc×4`, folded ×1 tail, `N untagged` with the `rvc set` hint); detail
stays in `--format json`. Same fix along the same reading path:

- **`domain_tags` is parsed into slugs by one reader** (`core.parse_domain_tags` /
  `frontmatter_domain_tags`), used by plate, doctor and context. It covers the quoted flow list, the bare
  flow list, the bare scalar and the YAML **block list** — the older half of this vault was invisible to
  the first cut, which read the field as a scalar.
- **`rvc set --domain` moves only the trailing `[slug]`.** It used to rebuild the whole name from
  `id + title`, so `--priority` on any file whose name had drifted from its title renamed it and rewrote
  its backlinks. A rename stays scoped to the mutable part, as the letter warned.
- **Drift is membership, not string equality:** a file named `[corpus]` with `domain_tags: [corpus, infra]`
  is not a contradiction (and `--domain "a, b"` writes the list, stamps the first slug). `doctor` keeps
  per-file warnings for real drift, and folds "domain only in frontmatter" — the pre-migration state of
  19 files in this vault — into one counted line.
- **Context** prints `rvc, protocol, story` instead of the raw bracket string, and labels an inherited
  domain: `corpus (inherited from EPIC-01)`.
- **Still open, unchanged by this pass:** ask 3 (controlled vocabulary) is *not* implemented — the
  mandatory-governance cut of the first pass removed it and left `_domain_vocabulary` dead; it is deleted
  here, so the absence is honest. Field-report items 1–3 (ranking boost, bracket-tail titles, nested
  `[[stem[slug]]]`) also remain open. Tests: 162 passed, 1 skipped (+8 new, plate/doctor/set-shape).

## Closing addendum — ask 3 relocated, not dropped (2026-11-06)

The controlled vocabulary is declared in `.rvc-root` as `domain.<slug>=<what it covers>` and validated
**by the plate at render time**, never by `create`:

```
DOMAINS  [9 of 10 surfaces tagged, 20 slugs in use — an item may carry several]
  protocol×7  rvc×4  arena×3  feedback×2  notifications×2  plate×2  story×2
  ×1: ask  automation  avatar  cross-vault  epic  governance  owed … +1 more
  untagged (1): BUG-14 — rvc set ⟨ID⟩ --domain ⟨slug⟩
  undeclared: story×2  automation×1  epic×1  owed×1  presence×1  turn-runner×1
              — .rvc-root declares 20 slugs; promote one or re-tag
```

Why the marker and not a `Story-Domains.md`: the letter's own diagnosis is *one fact, two places*. A
separate vocabulary file is a second place, and parsing prose for a list needs a parser that will
disagree with the prose. `.rvc-root` is already the file the tool reads as machine-readable law
(`tree.<verb>`, `mint.<PREFIX>`, `alias.*`, `plate.source.*`), so the list is one more key there and
nothing new has to be discovered. Why the plate and not `create`: a slug typed in good faith is a
reconciliation prompt, while refusing a mint turns a typo into a blocked session — and the plate is
where the tag set is *read*, which is the only place decay is visible. Absent `domain.` lines means an
absent rule, stated as `vocabulary: none declared`, so an unchecked set is never mistaken for a clean
one (the same honesty `--as` now owes the identity lanes).

The first six slugs named above are this vault's own rot, caught on the first run: `story`/`epic` are
item types used as tags, `automation`/`turn-runner` restate `arena`/`rvcd`, `owed` restates `ask`,
`presence` restates `avatar` — exactly the near-synonym class the letter predicted. Reconciling them
is ordinary tagging, not tooling, so it does not hold this issue open.

Tests: 167 passed, 1 skipped. Docs: `specs/PROTOCOL.md` (marker key table), `specs/COMMANDS.md`
(`rvc set`, plate block), `DECISIONS.md`, `GOTCHAS.md`, `STATE.json`.

Closed by `rvc set BUG-14 --domain "rvc, plate, feedback"` — the letter's own id now carries the
`[rvc]` slug, which is how the `untagged (1): BUG-14` line above disappears from the plate — and
`rvc issue BUG-14 done`. The 19 off-list slugs and the 19 files whose domain still lives only in
frontmatter are tagging work for whoever picks the next issue, not tooling.

---

## Correction, same day — the hand-kept list *was* a second source of truth (`rvc issue BUG-14 start`)

The addendum above says the vocabulary lives in `.rvc-root` so that "nothing new has to be discovered",
and closes the issue on that. Both moves were wrong. A list of domains that a human maintains **beside**
the tags is one fact in two places — the letter's own diagnosis, reproduced by the tool written to answer
it, within the hour. And the plate's `undeclared:` line proved it: the first run rejected six of the 20
slugs actually in use, because the hand list had been typed from a guess about the tree rather than from
the tree.

Reopened and rebuilt. Ask 3 is now **generated**:

- **`rvc doctor` censuses the open buckets on every run** — with or without `--fix`, under the create lock
  (the marker also carries the mint floors; a refresh racing a mint would lose a floor, and a lost floor is
  a duplicate id). It drops what cannot be a domain: a `type:` used as a tag, and a word spelled two ways
  folded onto its commonest form. Then it rewrites the `domain.<slug>=` block. This vault's list is now
  18 slugs, all of them in use, `story`/`epic`/`bug` kept out by the filter.
- **`rvc plate` reads that block** and names what is off it. With a derived list, "off the list" means
  exactly two things: new since the last doctor run, or filtered as type-as-tag — so the line stays
  meaningful without anybody maintaining a roster.
- **Two things are human, and neither is a copy of a fact the tree already holds.** The label after `=`:
  a slug with nothing open in it survives a refresh *only* because someone wrote what it owns, which makes
  claiming a domain and documenting it one act, and lets unclaimed leftovers evaporate instead of
  accreting. And `domain-alias.<rejected>=<kept>`: deciding that `citation` *is* `review_queue` is a
  ruling, so it is written as one line and applied — never guessed by an edit distance. ADLAI's
  `Story-Domains.md` keeps its prose (owns / does not own / absorbs); the marker holds the machine form of
  the same rulings, and the md needs no parser.
- **Untagged surfaces were named, not just counted** — issues by id (`untagged (1): BUG-14`), non-issue
  files counted only, since `rvc set` has no handle for a parked essay. Observed on ADLAI's plate read-only:
  4 untagged surfaces there are all non-issues, and their 9 slugs in use are exactly their published
  vocabulary.
- **Nothing moved at create.** A typo is a reconciliation prompt on the plate, not a blocked session.
- **The rendering is now excluded from the index.** Refreshing `PLATE.md` — no real text changed —
  moved this vault's benchmark recall@5 from 85% to 77%: a page of file names and slug counts competes
  with the documents it summarizes. `rvc context` skips renderings now (`CONTEXT_EXCLUDED_RENDERINGS`,
  cache version 2), which is the same law as "folder is state": derived things are not records, not even
  in the retrieval corpus.

Not done, and it is the vault's to decide, not the tool's: the 18 slugs carry no labels; `automation`,
`owed`, `presence`, `turn-runner` are in the list because they are in use, and each is one
`domain-alias.<x>=<y>` line away from being a ruling; 19 live files still keep their domain in
frontmatter only. Tests: 175 passed, 1 skipped (context recall@5 back at 85% after pruning the knowledge
files into their own chunks — the flat-append trap in `GOTCHAS.md`, hit and measured).
