---
id: BUG-14
title: FEEDBACK-rvc — deposit from ADLAI (STORY-162)
type: bug
priority: P2
origin: adlai-vault
submitted: 2026-11-06
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

