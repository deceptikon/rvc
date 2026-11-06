"""Vault constitution audit and automated repair."""

import os
import sys
import re

from rvc.core import (
    resolve_tree, tree_dirs, hot_dirs, LEGACY_PRIORITY_TO_P,
    _parse_domain_from_filename, frontmatter_domain_tags, domain_slug_key,
    read_domain_vocabulary, read_domain_aliases, write_domain_vocabulary,
    vault_create_lock,
)
from rvc.plate import plate_frontmatter

# ── Constitution audit: `rvc doctor` (STORY-029) ─────────────────────────────
# Folder = state. On a tree that declares a `block` bucket (newvault-shaped), a
# `status:` frontmatter field is a refusal-grade violation and any `priority:`
# outside the P0-P3 vocabulary is drift. Legacy trees (no block bucket) keep
# their old filing conventions — this guard exists only where the law says the
# folder owns state.

P_VOCABULARY = ("P0", "P1", "P2", "P3")


def _fold_priority(value):
    """Fold a stray priority into the P0-P3 vocabulary; None if not recognisable."""
    v = (value or "").strip()
    if v in P_VOCABULARY:
        return v
    legacy = {k.lower(): p for k, p in LEGACY_PRIORITY_TO_P.items()}
    if v.lower() in legacy:
        return legacy[v.lower()]
    m = re.match(r"^P(\d+)(\.\d+)*$", v, re.IGNORECASE)
    if m:
        tier = min(int(m.group(1)), 3)
        return f"P{tier}"
    return None


def _doctor_rewrite(text):
    """Inside the --- frontmatter block: drop `status:`, fold `priority:`.

    Returns (new_text, changed, had_status, folded_priority). Only the
    frontmatter block is touched; body and other lines pass through exactly.
    """
    if not text.startswith("---"):
        return text, False, False, None
    end = text.find("\n---", 3)
    if end == -1:
        return text, False, False, None
    raw = text[3:end].strip("\n")
    body = text[end:]
    out_lines = []
    changed = False
    had_status = False
    folded = None
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not m:
            out_lines.append(line)
            continue
        key, val = m.group(1), m.group(2).strip().strip("\"'")
        if key.lower() == "status":
            had_status = True
            changed = True
            continue  # drop the line — folder owns state
        if key.lower() == "priority" and val not in P_VOCABULARY:
            new_val = _fold_priority(val)
            if new_val and new_val != val:
                out_lines.append(f"priority: {new_val}")
                changed = True
                folded = new_val
                continue
        out_lines.append(line)
    new_text = "---\n" + "\n".join(out_lines) + body
    return new_text, changed, had_status, folded


# ── Domain vocabulary: generated, never hand-kept ────────────────────────────
# BUG-14 ask 3 wanted a controlled list. A list a human keeps in `.rvc-root` (or
# in a spec file) is a second place for the same fact, and the letter's own
# diagnosis is that two places disagree eventually. So the list is *derived*:
# `rvc doctor` censuses the live buckets, filters what cannot be a domain, and
# rewrites the `domain.<slug>=` block. `rvc plate` then validates against what
# doctor wrote. Only the label after `=` is human, and only that survives.

DOMAIN_TYPE_SUFFIXES = ("s", "es")
# The buckets whose tags vote on the vocabulary — the same lanes `rvc plate` reads.
# A closed issue's tags are evidence of what was done, not a claim about what the
# vault works in now, so the done lane and the archives are out (ADLAI's own
# hygiene rule: never re-tag the archive; no domain for a subsystem with no open work).
DOMAIN_CENSUS_VERBS = ("create", "triage", "start", "block", "defer")


def _slug_tokens(slug):
    """Tokens of a slug, singular-folded, at least 3 chars long."""
    out = set()
    for token in domain_slug_key(slug).split("-"):
        if len(token) >= 3:
            out.add(token)
            for suffix in DOMAIN_TYPE_SUFFIXES:
                if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                    out.add(token[:-len(suffix)])
    return out


def _slug_distance(a, b):
    """Levenshtein distance — small strings only (slugs are short)."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def slug_variants(a, b):
    """True when two slugs look like the same domain spelled twice (a hint, not a ruling)."""
    tokens_a, tokens_b = _slug_tokens(a), _slug_tokens(b)
    if tokens_a & tokens_b:
        return True
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 4 and long_.startswith(short):
        return True
    return min(len(a), len(b)) >= 6 and _slug_distance(a, b) <= 2


def census_domains(vault_path, tree):
    """Census of the open buckets: counts per raw slug, files per slug, the type words.

    Only the buckets the plate reads (`DOMAIN_CENSUS_VERBS`): the done lane and the
    archives keep their historical tags as evidence and never vote on the list.
    The type words come from the vault's own `type:` fields and id prefixes, so
    `story`/`epic` are recognised as type-as-tag here instead of being hardcoded
    in the tool.
    """
    counts, files, type_words, multi = {}, {}, set(), 0
    for bucket in sorted({tree[v] for v in DOMAIN_CENSUS_VERBS if v in tree}):
        root = os.path.join(vault_path, bucket)
        if not os.path.isdir(root):
            continue
        for dirpath, _, names in os.walk(root):
            for fn in sorted(names):
                if not fn.endswith(".md"):
                    continue
                try:
                    with open(os.path.join(dirpath, fn), "r", errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                fields = plate_frontmatter(text)
                if fields.get("type"):
                    type_words.add(domain_slug_key(fields["type"]))
                id_prefix = re.match(r"^([A-Za-z]+)-\d", fn)
                if id_prefix:
                    type_words.add(id_prefix.group(1).lower())
                rel = os.path.relpath(os.path.join(dirpath, fn), vault_path)
                tags = frontmatter_domain_tags(text)
                if len(tags) > 1:
                    multi += 1
                for slug in tags:
                    counts[slug] = counts.get(slug, 0) + 1
                    files.setdefault(slug, []).append(rel.replace(os.sep, "/"))
    return counts, files, type_words, multi


def sanitize_domains(counts, type_words, aliases=None):
    """Fold variants, drop type-as-tag, apply the vault's absorb rulings.

    Returns ([(slug, count)], dropped, folded, absorbed). `aliases` is the human
    half (`domain-alias.<rejected>=<kept>`): the mechanical rules can only reject a
    type used as a tag or the same word spelled twice — deciding that `citation` *is*
    `review_queue` is a ruling, and the census defers to it.
    """
    aliases = {domain_slug_key(src): tgt for src, tgt in (aliases or {}).items() if tgt}
    counts = dict(counts)
    absorbed = {}
    for raw in sorted(counts):
        kept = aliases.get(domain_slug_key(raw))
        if kept and domain_slug_key(kept) != domain_slug_key(raw):
            counts[kept] = counts.get(kept, 0) + counts.pop(raw)
            absorbed[raw] = kept
    groups = {}
    for raw, n in counts.items():
        groups.setdefault(domain_slug_key(raw), []).append((raw, n))
    slugs, dropped, folded = [], [], {}
    for key, variants in groups.items():
        bare = key[:-1] if key.endswith("s") and len(key) > 3 else key
        if key in type_words or bare in type_words:
            dropped.extend(raw for raw, _ in variants)
            continue
        if key in aliases:  # ruled away, and nothing carried it here
            continue
        total = sum(n for _, n in variants)
        ranked = sorted(variants, key=lambda pair: (-pair[1], pair[0]))
        canonical = ranked[0][0]
        others = sorted(raw for raw, _ in variants if raw != canonical)
        if others:
            folded[canonical] = others
        slugs.append((canonical, total))
    for kept in aliases.values():  # a ruling declares its target, open work or not
        if domain_slug_key(kept) not in groups and domain_slug_key(kept) not in type_words:
            slugs.append((kept, 0))
    slugs.sort(key=lambda pair: (-pair[1], pair[0]))
    return slugs, sorted(dropped), folded, absorbed


def refresh_domain_vocabulary(vault_path, tree=None):
    """Rebuild the `.rvc-root` domain block from the tree; returns the audit dict.

    Run on every `rvc doctor`, with or without `--fix`: a *rendering* that goes stale
    is worse than one that does not exist, and the plate reads it.

    The read-modify-write of the marker happens under the create lock: a mint
    bumping `mint.<PREFIX>` at the same moment would otherwise be overwritten by this
    command's copy of the file, and a lost floor is a duplicate id — the worst failure
    this tool has (BUG-09). The rewrite itself is atomic, so a lock-free `resolve_tree`
    never sees a truncated marker.
    """
    tree = tree or resolve_tree(vault_path)
    counts, files, type_words, multi = census_domains(vault_path, tree)
    aliases = read_domain_aliases(vault_path)
    slugs, dropped, folded, absorbed = sanitize_domains(counts, type_words, aliases)
    skipped = None
    try:
        with vault_create_lock(vault_path):
            declared = read_domain_vocabulary(vault_path)
            entries, unlabeled, standing = {}, [], []
            for slug, _count in slugs:
                label = declared.get(slug)
                if label is None:
                    label = next((alt for raw, alt in declared.items()
                                  if domain_slug_key(raw) == domain_slug_key(slug)), None)
                label = label or ""
                if not label:
                    unlabeled.append(slug)
                entries[slug] = label
            # A label is an act of claiming: a slug with nothing open in it survives only
            # because a human wrote what it owns. Unlabeled leftovers of an older census
            # evaporate, so the list cannot quietly accrete dead domains — and a standing
            # domain (`ai_watch`, no open work yet) stands on the line that documents it.
            filtered = ({domain_slug_key(s) for s in dropped}
                        | {domain_slug_key(s) for s in absorbed}
                        | set(type_words)
                        | {domain_slug_key(t) for t in aliases.values()})
            for slug, label in declared.items():
                key = domain_slug_key(slug)
                if not label or key in entries or key in filtered:
                    continue
                entries[slug] = label
                standing.append(slug)
            pairs = sorted(entries.items())
            written = write_domain_vocabulary(vault_path, pairs)
    except TimeoutError as err:
        # A mint is in flight, so the marker cannot be touched. Say the refresh did
        # not happen rather than let the plate read a stale list in silence.
        skipped = str(err)
        pairs = sorted(read_domain_vocabulary(vault_path).items())
        written, unlabeled, standing = None, [], []
    named = sorted(slug for slug, _ in pairs)
    candidates = [(a, b) for i, a in enumerate(named) for b in named[i + 1:]
                  if slug_variants(a, b)]
    return {
        "declared": named,
        "written": bool(written),
        "dropped": dropped,
        "folded": folded,
        "absorbed": absorbed,
        "standing": sorted(standing),
        "unlabeled": unlabeled,
        "candidates": candidates,
        "multi_tag": multi,
        "files": files,
        "skipped": skipped,
    }


def cmd_doctor(vault_path, fix=False):
    """Audit live files against the vault's own constitution.

    On a tree that declares a `block` bucket, `status:` in a live file is a
    violation and off-vocabulary `priority:` is a warning. With fix=True both
    are repaired in place. Archive buckets are never touched.

    Returns {"newvault": bool, "violations": [...], "warnings": [...], "fixed": [...]}.
    """
    tree = resolve_tree(vault_path)
    newvault = "block" in tree
    report = {"newvault": newvault, "violations": [], "warnings": [], "fixed": []}
    unslugged = []  # files whose domain lives only in frontmatter — one line, not N
    # Always, not only with --fix: the vocabulary is a rendering of the tree, and
    # a rendering nobody regenerates is a lie waiting to happen.
    domains = refresh_domain_vocabulary(vault_path, tree)
    report["domains"] = domains
    for bucket in hot_dirs(tree):
        root = os.path.join(vault_path, bucket)
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, vault_path)
                try:
                    text = open(fp, "r", errors="replace").read()
                except OSError:
                    continue
                fields = plate_frontmatter(text)
                status_key = next((k for k in fields if k.lower() == "status"), None)
                priority = fields.get("priority")
                priority_off = newvault and priority is not None and priority not in P_VOCABULARY

                # Domain checks: the filename slug and the frontmatter field are
                # one fact in two places, so drift is a per-file warning. A file
                # that simply has no slug yet is the pre-migration state of the
                # whole tree (19 of them here) — counted, named once, not spammed.
                file_domain = _parse_domain_from_filename(fn)
                fm_tags = frontmatter_domain_tags(text)
                if file_domain and fm_tags and file_domain not in fm_tags:
                    report["warnings"].append(
                        f"{rel}: domain mismatch — filename '{file_domain}' not in "
                        f"frontmatter [{', '.join(fm_tags)}]")
                elif file_domain and not fm_tags:
                    report["warnings"].append(
                        f"{rel}: filename has domain '{file_domain}' but no domain_tags in frontmatter")
                elif fm_tags and not file_domain:
                    unslugged.append(rel)

                if not newvault:
                    continue  # legacy trees keep their filing conventions
                if fix:
                    if status_key is not None or priority_off:
                        new_text, changed, had_status, folded = _doctor_rewrite(text)
                        if changed and new_text != text:
                            with open(fp, "w") as f:
                                f.write(new_text)
                            parts = []
                            if had_status:
                                parts.append("stripped status:")
                            if folded:
                                parts.append(f"priority {priority} -> {folded}")
                            report["fixed"].append(f"{rel}: " + ", ".join(parts))
                else:
                    if status_key is not None:
                        report["violations"].append(
                            f"{rel}: status: field present — folder owns state (block tree)")
                    if priority_off:
                        fold = _fold_priority(priority)
                        hint = f" -> {fold}" if fold else " (no fold known)"
                        report["warnings"].append(
                            f"{rel}: priority {priority!r} off-vocabulary, expected P0-P3{hint}")

    if unslugged:
        noun = "file" if len(unslugged) == 1 else f"{len(unslugged)} files"
        verb = "has" if len(unslugged) == 1 else "have"
        shown = ", ".join(unslugged[:3])
        rest = f" … (+{len(unslugged) - 3} more)" if len(unslugged) > 3 else ""
        report["warnings"].append(
            f"{noun} {verb} domain_tags but no slug in filename: {shown}{rest}"
            " — rvc set ⟨ID⟩ --domain ⟨slug⟩ stamps the primary one")
    if domains["dropped"]:
        shown = ", ".join(domains["dropped"][:3])
        rest = f" … (+{len(domains['dropped']) - 3} more)" if len(domains["dropped"]) > 3 else ""
        report["warnings"].append(
            f"type-as-tag kept out of the vocabulary: {shown}{rest} — a domain names what "
            "an issue changes, not what the issue is")
    if domains["folded"]:
        shown = ", ".join(f"{can}←{', '.join(alt)}" for can, alt in list(domains["folded"].items())[:3])
        rest = f" … (+{len(domains['folded']) - 3} more)" if len(domains["folded"]) > 3 else ""
        report["warnings"].append(
            f"spelling variants folded: {shown}{rest} — the list keeps the commonest spelling; "
            "rvc set ⟨ID⟩ --domain ⟨slug⟩ follows it")
    if domains["skipped"]:
        report["warnings"].append(f"domain vocabulary NOT refreshed — {domains['skipped']}")
    if domains["absorbed"]:
        shown = ", ".join(f"{src}→{tgt}" for src, tgt in sorted(domains["absorbed"].items())[:3])
        rest = f" … (+{len(domains['absorbed']) - 3} more)" if len(domains["absorbed"]) > 3 else ""
        report["warnings"].append(
            f"ruled-away slug still in use: {shown}{rest} — the absorb is recorded, the "
            "files are not: rvc set ⟨ID⟩ --domain ⟨kept⟩")
    if domains["candidates"]:
        shown = ", ".join(f"{a}~{b}" for a, b in domains["candidates"][:3])
        rest = f" … (+{len(domains['candidates']) - 3} more)" if len(domains["candidates"]) > 3 else ""
        report["warnings"].append(
            f"slugs that look like one domain spelled twice: {shown}{rest} — rule on it with "
            "`domain-alias.<rejected>=<kept>` in .rvc-root, or leave both")
    return report

