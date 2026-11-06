"""Plate calculation, lane aggregation, and open asks scanner."""

import os
import sys
import re
import json
import datetime as dt
import subprocess

from rvc.core import (
    resolve_tree, tree_dirs, find_file_by_id, marker_file,
    frontmatter_domain_tags, read_domain_vocabulary, read_domain_aliases,
    domain_slug_key,
)

PLATE_ASK_LINE_RE = re.compile(r"^\s*-\s*\[ \]\s*(.*)$")
PLATE_HANDLE_RE = re.compile(r"@([\w.+-]+)")
PLATE_SEP_RE = re.compile(r"\s+[-—:]\s+")
PLATE_HEADER_RE = re.compile(r"^##\s+([^@\n]+?)\s*@\s*(\d{4}-\d{2}-\d{2})", re.M)
PLATE_DATE_RE = re.compile(r"^\s*(?:updated|date|created)\s*:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
PLATE_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
PLATE_ISSUE_TYPES = ("story", "epic", "bug", "task")
# Domain rows join on the id when the surface has one — `STORY-013`, not a
# 70-character filename. The lanes already carry paths; this section is an index.
PLATE_ITEM_ID_RE = re.compile(r"^([A-Z][A-Z0-9_]*-\d+)")
# The DOMAINS block is a histogram, not a listing: slugs carrying more than one
# item get a count entry, the ×1 tail is named and then folded, and file names
# never appear — they are already in the lanes above. Both rows wrap at width,
# so a 30-domain vault renders the same four lines a 6-domain one does.
PLATE_DOMAIN_LINE_WIDTH = 60
PLATE_DOMAIN_SINGLETONS_SHOWN = 12
PLATE_DOMAIN_UNTAGGED_SHOWN = 8
PLATE_DOMAIN_UNDECLARED_SHOWN = 8


def read_plate_config(vault_path):
    """Return (aliases, owner, sources, source_aliases) from `.rvc-root`.

    `sources` = {name: vault_path} from `plate.source.<name>=<path>` — external
    vaults the plate adds a derived feedback lane for (IDs and counts only, no
    content crosses). `source_aliases` = {name: prefix} from
    `plate.alias.<name>=<alias>` — display aliases for external issue IDs
    (BUG-14 shown as F-14 is "rendering, not a record").
    """
    aliases, owner = {}, None
    sources, source_aliases = {}, {}
    root_file = marker_file(vault_path) or os.path.join(vault_path, ".rvc-root")
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("alias."):
                    canonical, _, handles = line[len("alias."):].partition("=")
                    canonical = canonical.strip()
                    for handle in handles.split(","):
                        key = handle.strip().lstrip("@").lower()
                        if key:
                            aliases[key] = canonical
                elif line.startswith("plate.source."):
                    spec = line[len("plate.source."):]
                    name, _, path = spec.partition("=")
                    name, path = name.strip(), path.strip()
                    if name and path:
                        sources[name] = path
                elif line.startswith("plate.alias."):
                    spec = line[len("plate.alias."):]
                    name, _, alias = spec.partition("=")
                    name, alias = name.strip(), alias.strip()
                    if name and alias:
                        source_aliases[name] = alias
                elif line.startswith("plate.owner"):
                    owner = line.partition("=")[2].strip() or None
    return aliases, owner, sources, source_aliases


def resolve_alias(raw, aliases):
    """Canonicalize a handle typed by a human or stored in a doc; unknown handles pass through.

    Applied to *both* the `--as` argument and every ask box, so an unrecognized handle still compares
    equal on both sides — symmetry is what keeps a typo from silently dropping a thread.
    """
    if not raw:
        return None
    key = raw.strip().lstrip("@")
    if not key:
        return None
    canonical = aliases.get(key.lower())
    if canonical:
        return canonical
    for candidate in aliases.values():
        if candidate.lstrip("@").lower() == key.lower():
            return candidate
    return "@" + key


def plate_frontmatter(text):
    """Minimal `key: value` frontmatter read — issue files never need a YAML parser."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields = {}
    for line in text[3:end].splitlines():
        match = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if match and match.group(1) not in fields:
            fields[match.group(1)] = match.group(2).strip().strip("\"'")
    return fields


def plate_asks(text, aliases):
    """Open ask boxes as [(canonical, note)] — fenced text is never an ask."""
    asks, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = PLATE_ASK_LINE_RE.match(line)
        if not match:
            continue
        body = match.group(1)
        parts = PLATE_SEP_RE.split(body, maxsplit=1)
        head = parts[0]
        note = parts[1].strip() if len(parts) > 1 else ""
        handles = PLATE_HANDLE_RE.findall(head) or PLATE_HANDLE_RE.findall(body)
        asks.extend((resolve_alias(h, aliases), note) for h in handles)
    return asks


def plate_last_activity(text, fields):
    """Latest `## <Author>@<date>` section, else the newest frontmatter date."""
    headers = PLATE_HEADER_RE.findall(text)
    for candidate in ([headers[-1][1]] if headers else []) + PLATE_DATE_RE.findall(text):
        try:
            return dt.date.fromisoformat(candidate)
        except ValueError:
            continue
    stamp = fields.get("updated") or fields.get("created") or fields.get("date")
    try:
        return dt.date.fromisoformat(stamp) if stamp else None
    except ValueError:
        return None


def plate_surface(fpath, vault_path, aliases):
    try:
        with open(fpath, "r", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    fields = plate_frontmatter(text)
    type_name = fields.get("type", "")
    name = os.path.basename(fpath)
    headers = PLATE_HEADER_RE.findall(text)
    return {
        "path": os.path.relpath(fpath, vault_path).replace(os.sep, "/"),
        "name": name,
        "type": type_name,
        "priority": fields.get("priority", ""),
        "domain_tags": frontmatter_domain_tags(text),
        "is_issue": type_name in PLATE_ISSUE_TYPES or name.startswith(("STORY-", "EPIC-")),
        "asks": plate_asks(text, aliases),
        "open_boxes": len(re.findall(r"^\s*(?:[-*]|\d+\.)\s*\[ \]", text, re.M)),
        "done_boxes": len(re.findall(r"^\s*(?:[-*]|\d+\.)\s*\[[xX]\]", text, re.M)),
        "last": plate_last_activity(text, fields),
        "last_speaker": headers[-1][0].strip() if headers else "",
    }


def _plate_rows(entries, width=PLATE_DOMAIN_LINE_WIDTH):
    """Pack short entries into rows of at most `width` characters (two-space separated)."""
    rows, row, used = [], [], 0
    for entry in entries:
        need = len(entry) + (2 if row else 0)
        if row and used + need > width:
            rows.append("  ".join(row))
            row, used, need = [], 0, len(entry)
        row.append(entry)
        used += need
    if row:
        rows.append("  ".join(row))
    return rows


def _plate_emit(lines, entries, first="  ", width=PLATE_DOMAIN_LINE_WIDTH, cont=None):
    """Append wrapped `entries` to `lines`; continuation rows align under `first`."""
    cont = " " * len(first) if cont is None else cont
    for i, row in enumerate(_plate_rows(entries, width)):
        lines.append((first if i == 0 else cont) + row)


def get_recent_vault_commits(vault_path, count=5):
    """Retrieve the last N commits touching the vault directory."""
    if count <= 0:
        return []
    try:
        res = subprocess.run(
            ["git", "log", f"-n{count}", "--pretty=format:%h%x09%cr%x09%an%x09%s", "--", "."],
            cwd=vault_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return []
        commits = []
        for line in res.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "relative_time": parts[1],
                    "author": parts[2],
                    "subject": parts[3],
                })
        return commits
    except Exception:
        return []


def _external_bug_items(src_vault):
    """All BUG-* items in an external vault as [{path, done}], or None if not a vault.

    Folder position inside the external vault's own tree decides done vs pending
    (folder owns state there too); nothing but IDs ever leaves the source vault.
    """
    if not os.path.isdir(src_vault):
        return None
    try:
        src_tree = resolve_tree(src_vault)
    except Exception:
        return None
    done_dirs = {src_tree.get(k) for k in ("done", "evict", "supersede") if src_tree.get(k)}
    items = []
    for root, dirs, files in os.walk(src_vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if not (fname.startswith("BUG-") and fname.endswith(".md")):
                continue
            rel = os.path.relpath(root, src_vault).replace(os.sep, "/")
            path = f"{rel}/{fname}" if rel != "." else fname
            items.append({
                "path": path,
                "done": any(path.startswith(d + "/") for d in done_dirs),
            })
    return items


def _lane_domains_badge(rows, max_shown=4):
    """Compact summary of domain tags present in this lane's items."""
    slug_counts = {}
    for r in rows:
        for t in r.get("domain_tags", []):
            slug_counts[t] = slug_counts.get(t, 0) + 1
    if not slug_counts:
        return ""
    sorted_slugs = sorted(slug_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    all_single = all(cnt == 1 for _, cnt in sorted_slugs)
    shown = sorted_slugs[:max_shown]
    parts = [tag if all_single else f"{tag}({cnt})" for tag, cnt in shown]
    extra = len(sorted_slugs) - len(shown)
    if extra > 0:
        parts.append(f"+{extra}")
    return "  [" + " ".join(parts) + "]"


def cmd_plate(vault_path, as_alias=None, fmt="text", stale_days=7, today=None, log_count=5, write=False):
    """Render the plate: seven lanes computed from folders, priorities and open ask boxes."""
    tree = resolve_tree(vault_path)
    aliases, owner, sources, source_aliases = read_plate_config(vault_path)
    me = resolve_alias(as_alias, aliases) if as_alias else None
    today = today or dt.date.today()

    watched = {
        "inbox": tree.get("create"),
        "next": tree.get("triage"),
        "active": tree.get("start"),
        "decide": tree.get("block"),
        "deferred": tree.get("defer"),
    }
    surfaces = []
    for rel_dir in [d for d in watched.values() if d]:
        base = os.path.join(vault_path, rel_dir)
        if not os.path.isdir(base):
            continue
        for root, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in sorted(filenames):
                if not fname.endswith(".md") or fname.startswith("_"):
                    continue  # shapes are not surfaces
                surface = plate_surface(os.path.join(root, fname), vault_path, aliases)
                if surface:
                    surfaces.append(surface)

    lanes = {k: [] for k in ("owes_turn", "owner", "active", "next", "waiting", "overdue", "inbox")}
    decide = watched["decide"] or ""
    waiting_paths = set()

    for surface in surfaces:
        rel = surface["path"]
        in_decide = bool(decide) and rel.startswith(decide + "/")
        sub = rel[len(decide) + 1 :].split("/")[0] if in_decide else ""
        is_deliberation = in_decide and sub in ("tables", "debates", "reviews")

        for canonical, note in surface["asks"]:
            row = dict(surface)
            row["ask"] = note
            if owner and canonical == owner:
                # Reading as the owner, the verdict asks *are* your turns — not a third lane,
                # and not dropped between the two.
                (lanes["owes_turn"] if me == owner else lanes["owner"]).append(row)
            elif me and canonical == me:
                lanes["owes_turn"].append(row)

        if rel.startswith((watched["inbox"] or "?") + "/"):
            lanes["inbox"].append(surface)
        elif rel.startswith((watched["active"] or "?") + "/") and surface["is_issue"]:
            lanes["active"].append(surface)
        elif rel.startswith((watched["next"] or "?") + "/") and surface["is_issue"]:
            lanes["next"].append(surface)
        elif in_decide and not is_deliberation:
            # Blocked decisions (issues) and proposals both await a ruling — the
            # owner's clock, not the vault's (stories were dropped here before
            # STORY-031; ADLAI's DQL "Awaiting a ruling" lists all of 40_DECIDE).
            lanes["waiting"].append(surface)
            waiting_paths.add(rel)
        elif rel.startswith((watched["deferred"] or "?") + "/"):
            # A park is a park: ANY file parked in the deferred bucket renders
            # (issues and non-issues alike — the measured blind spot was an
            # ESSAY the plate could not see, FEEDBACK-rvc 2026-11-05). The
            # bucket tag in the render tells a park from a ruling.
            lanes["waiting"].append(surface)
            waiting_paths.add(rel)

    for surface in surfaces:
        if surface["path"] in waiting_paths or not surface["last"]:
            continue
        aged = (today - surface["last"]).days
        on_surface = surface["path"].startswith((decide or "?") + "/") or surface["path"].startswith(
            (watched["active"] or "?") + "/"
        )
        if aged >= stale_days and on_surface:
            lanes["overdue"].append(dict(surface, age_days=aged))

    lanes["next"].sort(key=lambda s: (PLATE_PRIORITY_ORDER.get(s["priority"], 9), s["name"]))
    lanes["active"].sort(key=lambda s: s["name"])
    lanes["waiting"].sort(key=lambda s: s["name"])
    lanes["inbox"].sort(key=lambda s: s["name"])
    lanes["overdue"].sort(key=lambda s: -s["age_days"])
    lanes["owner"].sort(key=lambda s: s["path"])
    lanes["owes_turn"].sort(key=lambda s: s["path"])

    # External feedback lanes: derived from other vaults' trees — IDs and counts
    # only, no content crosses. A client vault configures
    # `plate.source.<name>=<vault>` to see the feedback it filed against a tool,
    # aliased for provenance (`plate.alias.<name>=F` renders BUG-14 as F-14).
    external = []
    for name, src_vault in sorted(sources.items()):
        items = _external_bug_items(src_vault)
        if items is None:
            print(f"[RVC] Warning: plate.source.{name} is not a vault: "
                  f"{src_vault}", file=sys.stderr)
            continue
        alias = source_aliases.get(name)
        pending, done = [], 0
        for item in items:
            fname = item["path"].rsplit("/", 1)[-1]
            m = re.match(r"^BUG-(\d+)", fname)
            if not m:
                continue
            if item["done"]:
                done += 1
            else:
                pending.append(f"{alias}-{m.group(1)}" if alias else fname.split(".md")[0])
        pending.sort(key=lambda s: int(s.rsplit("-", 1)[1]))
        external.append({
            "name": name,
            "vault": src_vault,
            "pending": pending,
            "done": done,
            "total": done + len(pending),
        })

    recent_commits = get_recent_vault_commits(vault_path, count=log_count)

    # Domain histogram: one row per slug, items counted not enumerated. Grouping
    # on the raw frontmatter string made every multi-tag issue its own "domain"
    # and printed full file names — a dump of the tag field, not a summary.
    domain_map = {}  # slug -> [item label, ...]
    untagged_labels, untagged_issues = [], []
    tagged = 0
    for surface in surfaces:
        tags = surface["domain_tags"]
        id_match = PLATE_ITEM_ID_RE.match(surface["name"])
        label = id_match.group(1) if id_match else surface["name"]
        if tags:
            tagged += 1
        else:
            untagged_labels.append(label)
            if surface["is_issue"]:
                untagged_issues.append(label)
        for tag in tags:
            domain_map.setdefault(tag, []).append(label)
    domain_counts = sorted(
        ((tag, names) for tag, names in domain_map.items()),
        key=lambda kv: (-len(kv[1]), kv[0]),
    )
    untagged = len(surfaces) - tagged
    # Ask 3, relocated: the vocabulary is *declared* in `.rvc-root` (the file the
    # tool already reads law from — tree verbs, mint floors, aliases) and checked
    # only here, at render time. No second file, no markdown parser, and nothing
    # refused at create: an undeclared slug is a decision to make, not a mint to
    # block. No `domain.` lines means no vocabulary and the plate says so.
    vocabulary = read_domain_vocabulary(vault_path)
    ruled = {domain_slug_key(src): tgt for src, tgt in read_domain_aliases(vault_path).items()}
    undeclared = [dict(domain=tag, count=len(names))
                  for tag, names in domain_counts if tag not in vocabulary]

    if fmt == "json":
        payload = {
            "vault": vault_path,
            "as": me,
            "owner": owner,
            "today": today.isoformat(),
            "identity_lanes": bool(me),
            "recent_activity": recent_commits,
            "domains": {
                "surfaces": len(surfaces),
                "tagged": tagged,
                "untagged": untagged,
                "untagged_items": sorted(untagged_labels),
                "vocabulary": {
                    "declared": len(vocabulary),
                    "slugs": [{"domain": slug, "label": label}
                              for slug, label in sorted(vocabulary.items())],
                    "aliases": [{"slug": src, "into": tgt}
                                for src, tgt in sorted(ruled.items())],
                },
                "undeclared": [{**row, "into": ruled.get(domain_slug_key(row["domain"]))}
                               for row in undeclared],
                "slugs": [{"domain": tag, "count": len(names), "items": sorted(names)}
                          for tag, names in domain_counts],
            },
            "lanes": {
                key: [
                    {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in row.items() if k != "asks"}
                    for row in rows
                ]
                for key, rows in lanes.items()
            },
            "external": {
                ext["name"]: {k: v for k, v in ext.items() if k != "name"}
                for ext in external
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    titles = {
        "owes_turn": f"YOU OWE A TURN (as {me})" if me else "YOU OWE A TURN (identity-free: pass --as)",
        "owner": "AWAITING THE OWNER",
        "active": "ACTIVE (WIP cap 2)",
        "next": "NEXT — the queue",
        # The lane holds two kinds of not-late: 40_DECIDE items blocked on a
        # ruling and 50_DEFERRED items parked on purpose. The old title named
        # only the park, so a blocked ruling read as "deferred on purpose"
        # (FEEDBACK-rvc 2026-11-05) — rows carry a bucket tag to tell them apart.
        "waiting": "WAITING — on a ruling (40_DECIDE) or parked on purpose (50_DEFERRED); not late",
        "overdue": f"OVERDUE — no new section ≥ {stale_days} days",
        "inbox": "INBOX — deposits, acknowledged not actionable",
    }
    lines = [f"PLATE — {os.path.basename(vault_path)} — {today.isoformat()} — derived from the tree"]
    for key, rows in lanes.items():
        if not rows and key in ("owes_turn", "owner", "overdue"):
            continue
        badge = _lane_domains_badge(rows) if rows else ""
        lines.append(f"\n{titles[key]}  [{len(rows)}]{badge}")
        if not rows:
            lines.append("  —")
            continue
        for row in rows:
            if key in ("owes_turn", "owner"):
                ask = f" — {row['ask']}" if row.get("ask") else ""
                lines.append(f"  {row['path']}{ask}")
            elif key == "active":
                lines.append(f"  {row['name']}  open={row['open_boxes']} done={row['done_boxes']}")
            elif key == "next":
                lines.append(f"  {row['priority'] or '—':>3}  {row['name']}")
            elif key == "waiting":
                bucket = row["path"].split("/")[0]
                lines.append(f"  [{bucket}] {row['name']}  pri={row['priority'] or '—'}")
            elif key == "overdue":
                lines.append(f"  {row['age_days']:>3}d  {row['path']}  (last: {row['last_speaker']})")
            elif key == "inbox":
                type_name = row.get("type", "")
                type_str = f"  type={type_name}" if type_name and type_name not in ("story", "bug", "epic", "") else ""
                lines.append(f"  {row['name']}{type_str}")
            else:
                lines.append(f"  {row['name']}  pri={row['priority'] or '—'}")

    # Domain histogram — counts only; the rows themselves live in the lanes above.
    total_issues = [s for s in surfaces if s["is_issue"]]
    tagged_issues = [s for s in total_issues if s["domain_tags"]]
    untagged_issues = [
        (PLATE_ITEM_ID_RE.match(s["name"]).group(1) if PLATE_ITEM_ID_RE.match(s["name"]) else s["name"])
        for s in total_issues if not s["domain_tags"]
    ]

    if surfaces and (domain_counts or untagged_issues):
        slug_word = "slug" if len(domain_counts) == 1 else "slugs"
        ratio_str = f"{len(tagged_issues)}/{len(total_issues)} issues tagged" if total_issues else f"{tagged}/{len(surfaces)} tagged"
        lines.append(f"\n---\nDOMAINS  [{ratio_str} · {len(domain_counts)} {slug_word}]")
        common = [f"{tag}×{len(names)}" for tag, names in domain_counts if len(names) > 1]
        singletons = [tag for tag, names in domain_counts if len(names) == 1]
        if common:
            _plate_emit(lines, common)
        if singletons:
            shown = singletons[:PLATE_DOMAIN_SINGLETONS_SHOWN]
            rest = f" … +{len(singletons) - len(shown)} more" \
                if len(singletons) > len(shown) else ""
            lines.append(f"  ×1: {', '.join(shown)}{rest}")
        if untagged_issues:
            named = sorted(untagged_issues)
            shown = named[:PLATE_DOMAIN_UNTAGGED_SHOWN]
            rest = f" … +{len(named) - len(shown)} more" if len(named) > len(shown) else ""
            lines.append(f"  untagged ({len(named)}): {', '.join(shown)}{rest} — rvc set <ID> --domain <slug>")
        if vocabulary:
            if undeclared:
                named = []
                for row in undeclared:
                    target = ruled.get(domain_slug_key(row["domain"]))
                    entry = f"{row['domain']}×{row['count']}"
                    named.append(f"{entry}→{target}" if target else entry)
                shown = named[:PLATE_DOMAIN_UNDECLARED_SHOWN]
                rest = f" … +{len(named) - len(shown)} more" if len(named) > len(shown) else ""
                lines.append(f"  undeclared: {', '.join(shown)}{rest} (run: rvc doctor)")
        else:
            lines.append("  vocabulary: none declared (run: rvc doctor)")

    if external:
        lines.append("\n---\nEXTERNAL FEEDBACK")
        for ext in external:
            pending_txt = ", ".join(ext["pending"]) if ext["pending"] else "—"
            pending_count = len(ext["pending"])
            lines.append(f"  {ext['name']}: pending: {pending_txt} ({pending_count}) · "
                         f"done: {ext['done']} of {ext['total']}")

    if recent_commits:
        lines.append(f"\n---\nRECENT ACTIVITY (last {len(recent_commits)} commits)")
        for c in recent_commits:
            lines.append(f"  {c['hash']}  {c['relative_time']:<14} ({c['author']}) {c['subject']}")

    rendered = "\n".join(lines)
    print(rendered)

    # STORY-034 AC3: the constitution calls PLATE.md "a rendering, not a record";
    # --write refreshes it from the tree so it cannot silently rot. Only the text
    # rendering is persistable — JSON is a data payload, not a plate document.
    if write:
        if fmt != "text":
            print("[RVC] Warning: --write persists the text rendering only; "
                  "ignored for --format json.", file=sys.stderr)
        else:
            plate_dir = tree.get("roadmap") or "10_CONTEXT"
            plate_path = os.path.join(vault_path, plate_dir, "PLATE.md")
            os.makedirs(os.path.dirname(plate_path), exist_ok=True)
            with open(plate_path, "w") as f:
                f.write(rendered + "\n")
            print(f"[RVC] Wrote plate rendering: {plate_path}")


