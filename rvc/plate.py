"""Plate calculation, lane aggregation, and open asks scanner."""

import os
import sys
import re
import json
import datetime as dt
import subprocess

from rvc.core import resolve_tree, tree_dirs, find_file_by_id

PLATE_ASK_LINE_RE = re.compile(r"^\s*-\s*\[ \]\s*(.*)$")
PLATE_HANDLE_RE = re.compile(r"@([\w.+-]+)")
PLATE_SEP_RE = re.compile(r"\s+[-—:]\s+")
PLATE_HEADER_RE = re.compile(r"^##\s+([^@\n]+?)\s*@\s*(\d{4}-\d{2}-\d{2})", re.M)
PLATE_DATE_RE = re.compile(r"^\s*(?:updated|date|created)\s*:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
PLATE_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
PLATE_ISSUE_TYPES = ("story", "epic", "bug", "task")


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
    root_file = os.path.join(vault_path, ".rvc-root")
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
        "is_issue": type_name in PLATE_ISSUE_TYPES or name.startswith(("STORY-", "EPIC-")),
        "asks": plate_asks(text, aliases),
        "open_boxes": len(re.findall(r"^\s*-\s*\[ \]", text, re.M)),
        "done_boxes": len(re.findall(r"^\s*-\s*\[[xX]\]", text, re.M)),
        "last": plate_last_activity(text, fields),
        "last_speaker": headers[-1][0].strip() if headers else "",
    }


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
        elif rel.startswith((watched["deferred"] or "?") + "/") and surface["is_issue"]:
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

    if fmt == "json":
        payload = {
            "vault": vault_path,
            "as": me,
            "owner": owner,
            "today": today.isoformat(),
            "identity_lanes": bool(me),
            "recent_activity": recent_commits,
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
        "waiting": "WAITING — deferred on purpose (not late)",
        "overdue": f"OVERDUE — no new section ≥ {stale_days} days",
        "inbox": "INBOX — deposits, acknowledged not actionable",
    }
    lines = [f"PLATE — {os.path.basename(vault_path)} — {today.isoformat()} — derived from the tree"]
    for key, rows in lanes.items():
        lines.append(f"\n{titles[key]}  [{len(rows)}]")
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
            elif key == "overdue":
                lines.append(f"  {row['age_days']:>3}d  {row['path']}  (last: {row['last_speaker']})")
            elif key == "inbox":
                lines.append(f"  {row['name']}  type={row['type'] or '—'}")
            else:
                lines.append(f"  {row['name']}  pri={row['priority'] or '—'}")

    if external:
        lines.append("\nEXTERNAL FEEDBACK — derived from other vaults (IDs and counts only)")
        for ext in external:
            pending_txt = ", ".join(ext["pending"]) if ext["pending"] else "—"
            lines.append(f"  {ext['name']}: pending: {pending_txt} | "
                         f"done: {ext['done']} of {ext['total']}")

    if recent_commits:
        lines.append(f"\nRECENT ACTIVITY (last {len(recent_commits)} commits)")
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


