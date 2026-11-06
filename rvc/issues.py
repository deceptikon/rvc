"""Issue lifecycle operations: creation, transitions, querying, and retrieval."""

import os
import shlex
import sys
import re
import datetime

from rvc.core import (
    resolve_tree, tree_dirs, hot_dirs, state_label, run_cmd, find_git_root,
    find_file_by_id, vault_create_lock, _next_id, bump_mint_floor,
    LEGACY_PRIORITY_TO_P, STATUS_ALIAS
)
from rvc.git import sync_before, sync_after, is_tracked
from rvc.context import context_cache_path, context_cache_repath, context_cache_update
from rvc.plate import plate_frontmatter

# Issue types recognized by the issue lifecycle (aligned with `rvc create --type`
# and PLATE_ISSUE_TYPES). Any other `type:` (proposal, feedback, note, …) has no
# bucket mapping — triage refuses to park those and tells the operator to place
# them by hand (STORY-034 AC4).
RVC_ISSUE_TYPES = ("story", "epic", "bug", "task")


def cmd_get(vault_path, item_id):
    file_path = find_file_by_id(vault_path, item_id)
    if not file_path:
        print(f"Error: Item {item_id} not found in vault.")
        sys.exit(1)

    with open(file_path, 'r') as f:
        print(f.read())
    
    print("\n" + "="*40)
    print(f"💡 RVC NEXT STEP: To ingest all linked specifications and PRDs, run:")
    print(f"   rvc context {item_id}")
    print("="*40)


def cmd_issue_action(vault_path, issue_id, action, skip_ci=True):
    tree = resolve_tree(vault_path)
    if action not in tree:
        print(f"Error: invalid action '{action}' for this vault's tree.")
        print(f"        Valid actions: {', '.join(sorted(tree.keys()))}")
        sys.exit(1)

    # STORY-034 AC1: resolve the handle before *any* other output or side effect.
    # A miss must exit non-zero with "no issue matches <handle>" — never print a
    # transition line (a false green is worse than an error).
    file_path = find_file_by_id(vault_path, issue_id)
    if not file_path:
        print(f"Error: no issue matches {issue_id}", file=sys.stderr)
        sys.exit(1)

    # STORY-034 AC4: triage only routes issue files into the queue. A proposal (or
    # any non-issue document) has no bucket mapping in the tree — say so at triage
    # time instead of parking it in a bucket it does not belong to.
    if action == "triage":
        try:
            with open(file_path, "r", errors="replace") as f:
                doc_text = f.read()
        except OSError:
            doc_text = ""
        doc_type = plate_frontmatter(doc_text).get("type", "").strip().lower()
        if doc_type not in RVC_ISSUE_TYPES:
            print(f"Warning: type '{doc_type or '—'}' has no triage target — manual "
                  "placement required.", file=sys.stderr)
            sys.exit(1)

    sync_before(vault_path)

    target_rel = tree[action]
    target_folder = os.path.join(vault_path, target_rel)
    os.makedirs(target_folder, exist_ok=True)

    file_name = os.path.basename(file_path)
    new_file_path = os.path.join(target_folder, file_name)

    if os.path.abspath(file_path) != os.path.abspath(new_file_path):
        moved = False
        git_root = find_git_root(vault_path)
        src_tracked = bool(git_root) and is_tracked(git_root, file_path)
        if not src_tracked:
            # A deposit that was never committed (hand-placed, or a create whose
            # commit did not land): plain move with a friendly note. This used
            # to cascade raw `git mv failed (fatal: not under version control)`
            # and `could not stage` warnings before landing (STORY-129).
            print(f"[RVC] {os.path.basename(file_path)} is untracked — "
                  "plain move (no `git mv`).")
        elif git_root:
            rc, _, err = run_cmd(
                f"git mv {shlex.quote(file_path)} {shlex.quote(new_file_path)}", cwd=git_root)
            if rc == 0:
                moved = True
            else:
                print(f"[RVC] git mv failed ({err.strip()}); falling back to plain move.")
        if not moved:
            if git_root and src_tracked:
                run_cmd(f"git rm -f {shlex.quote(file_path)}", cwd=git_root)
            os.rename(file_path, new_file_path)

    label = state_label(new_file_path, vault_path)
    print(f"[RVC] Issue {issue_id} moved to {label} ({target_rel}).")

    if os.path.exists(context_cache_path(vault_path)):
        try:
            context_cache_repath(vault_path, file_path, new_file_path)
        except Exception:
            pass

    sync_after(vault_path, [file_path, new_file_path], f"rvc: Issue {issue_id} -> {label}", skip_ci=skip_ci)


def cmd_issue_list(vault_path, bucket_or_status=None, list_dir=None):
    tree = resolve_tree(vault_path)
    scan_dirs = None

    if list_dir:
        if list_dir not in tree_dirs(tree):
            print(f"Error: --dir '{list_dir}' is not a bucket of this vault's tree.")
            print(f"        Buckets: {', '.join(tree_dirs(tree))}")
            sys.exit(1)
        scan_dirs = [list_dir]
    elif bucket_or_status:
        verb = bucket_or_status.strip()
        key = verb.lower()
        if verb in tree:
            scan_dirs = [tree[verb]]
        elif key in STATUS_ALIAS:
            scan_dirs = [tree[STATUS_ALIAS[key]]]
        elif os.path.isdir(os.path.join(vault_path, bucket_or_status)):
            scan_dirs = [bucket_or_status]
        else:
            print(f"Error: '{bucket_or_status}' is neither a verb, a status, nor a bucket of this vault.")
            print(f"        Verbs: {', '.join(sorted(tree.keys()))}")
            print(f"        Status aliases: {', '.join(sorted(STATUS_ALIAS))}")
            sys.exit(1)
    else:
        scan_dirs = hot_dirs(tree)

    print(f"# RVC Issues List ({bucket_or_status or list_dir or 'All hot buckets'})")
    found_any = False
    for d in scan_dirs:
        root = os.path.join(vault_path, d)
        if not os.path.isdir(root):
            continue
        for r, dirs, files in os.walk(root):
            for file in files:
                if not file.endswith(".md"):
                    continue
                file_path = os.path.join(r, file)
                print(f"- {file} [{state_label(file_path, vault_path)}]")
                found_any = True

    if not found_any:
        print("No issues found.")


def _sanitize_filename(name):
    """Remove unsafe characters for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "-")


def _build_filename(issue_id, title, domain=None):
    """Build filename with optional trailing domain slug."""
    safe_title = _sanitize_filename(title)
    if domain:
        return f"{issue_id}-{safe_title}[{domain}].md"
    return f"{issue_id}-{safe_title}.md"


def cmd_create_issue(vault_path, title, prefix=None, issue_type="story",
                     priority="Medium", body="", directory=None,
                     epic="", extra_frontmatter=None, skip_ci=True, domain=""):
    """Create a new issue file with proper frontmatter."""
    if prefix is None:
        # BUG-04: the id prefix follows the type (bug -> BUG, epic -> EPIC),
        # unless the caller pinned one explicitly via --prefix.
        prefix = {"bug": "BUG", "epic": "EPIC"}.get((issue_type or "story").lower(), "STORY")
    tree = resolve_tree(vault_path)
    if "block" in tree and priority in LEGACY_PRIORITY_TO_P:
        translated = LEGACY_PRIORITY_TO_P[priority]
        print(f"[RVC] priority '{priority}' -> '{translated}' (this tree sorts P0-P3)")
        priority = translated

    if directory is None:
        directory = tree.get("create") or tree["triage"]
    else:
        candidates = [directory]
        if not directory.startswith("10_Issues"):
            candidates.append("10_Issues/" + directory)
        resolved = next((c for c in candidates if c in tree_dirs(tree)), None)
        if resolved is None:
            print(f"Error: --dir '{directory}' is not a bucket of this vault's tree.")
            print(f"        Buckets: {', '.join(tree_dirs(tree))}")
            sys.exit(1)
        directory = resolved

    target_dir = os.path.join(vault_path, directory)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    mint_marker = None

    try:
        with vault_create_lock(vault_path):
            issue_id = _next_id(vault_path, prefix)
            # BUG-04: raise the prefix's high-water mark so a later rename
            # across prefixes can never free this number for reuse.
            num = int(issue_id.split("-", 1)[1])
            mint_marker = bump_mint_floor(vault_path, prefix, num)
            filename = _build_filename(issue_id, title, domain)
            filepath = os.path.join(target_dir, filename)

            if os.path.exists(filepath):
                print(f"Error: File already exists: {filepath}")
                sys.exit(1)

            today = datetime.date.today().isoformat()
            lines = [
                "---",
                f"id: {issue_id}",
                f"title: {title}",
                f"type: {issue_type}",
                f"priority: {priority}",
            ]
            if epic:
                lines.append(f"epic: [[{epic}]]")
            if domain:
                lines.append(f"domain_tags: {domain}")
            lines.append(f"started: {today}")
            if extra_frontmatter:
                if "block" in tree:
                    for k in extra_frontmatter:
                        if k.strip().lower() == "status":
                            print("Error: refusing to mint a `status:` field — this tree declares a `block` bucket,")
                            print("       and the folder owns state. Drop `status:` from extra_frontmatter.")
                            sys.exit(1)
                for k, v in extra_frontmatter.items():
                    lines.append(f"{k}: {v}")
            lines.append("---")
            lines.append("")
            lines.append(f"# {issue_id}: {title}")
            lines.append("")
            if body:
                body_text = body.replace("\\n", "\n").lstrip("\n")
                # The canonical `# {issue_id}: {title}` heading is emitted
                # above. Drop one redundant leading H1 the body may carry so it
                # renders once instead of twice (STORY-130 --body).
                head, sep, rest = body_text.partition("\n")
                if head.lstrip().startswith("# "):
                    body_text = rest.lstrip("\n")
                lines.append(body_text if body_text else "")
            else:
                lines.append("## Context")
                lines.append("")
                lines.append("## Acceptance Criteria")
                lines.append("- [ ] ")
                lines.append("")
                lines.append("## Test Case Requirements")

            with open(filepath, "w") as f:
                f.write("\n".join(lines) + "\n")
    except TimeoutError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if os.path.exists(context_cache_path(vault_path)):
        try:
            context_cache_update(vault_path)
        except Exception:
            pass

    print(f"[RVC] Created {filename}")
    print(f"      {filepath}")
    create_bucket = tree.get("create")
    hint_action = "triage" if (create_bucket and directory == create_bucket
                               and create_bucket != tree.get("triage")) else "start"
    print(f"      Hint: rvc issue {issue_id} {hint_action}")
    
    paths = [filepath]
    if mint_marker and os.path.abspath(mint_marker) != os.path.abspath(filepath):
        paths.append(mint_marker)
    sync_after(vault_path, paths, f"rvc: Created issue {issue_id}: {title}", skip_ci=skip_ci)
    
    return filepath


def _rewrite_frontmatter_field(text, key, value):
    """Replace or add a frontmatter field. Returns new text."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    body = text[end:]
    raw = text[3:end].strip("\n")
    out = []
    found = False
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m and m.group(1).lower() == key.lower():
            if value is None:
                continue  # remove field
            out.append(f"{m.group(1)}: {value}")
            found = True
        else:
            out.append(line)
    if not found and value is not None:
        out.append(f"{key}: {value}")
    return "---\n" + "\n".join(out) + body


def _rewrite_wikilinks(vault_path, old_stem, new_stem):
    """Replace [[old_stem]] / [[old_stem|...]] / [[old_stem#...]] in all .md files."""
    pat_link = re.compile(rf'\[\[{re.escape(old_stem)}\]\]')
    pat_hash = re.compile(rf'\[\[{re.escape(old_stem)}#([^\]]+)\]\]')
    pat_pipe = re.compile(rf'\[\[{re.escape(old_stem)}\|([^\]]+)\]\]')
    changed_any = False
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            try:
                text = open(fpath, "r", errors="replace").read()
            except OSError:
                continue
            new_text = pat_link.sub(f"[[{new_stem}]]", text)
            new_text = pat_hash.sub(f"[[{new_stem}#\\1]]", new_text)
            new_text = pat_pipe.sub(f"[[{new_stem}|\\1]]", new_text)
            if new_text != text:
                with open(fpath, "w") as f:
                    f.write(new_text)
                changed_any = True
    return changed_any


def cmd_set_issue(vault_path, issue_id, domain=None, epic=None, priority=None, skip_ci=True):
    """Edit mutable fields of an existing issue. Renames file if domain changes."""
    file_path = find_file_by_id(vault_path, issue_id)
    if not file_path:
        print(f"Error: Item {issue_id} not found in vault.")
        sys.exit(1)

    with open(file_path, "r", errors="replace") as f:
        text = f.read()

    fm = plate_frontmatter(text)
    orig_title = fm.get("title", "")
    orig_type = fm.get("type", "story")
    new_text = text
    renamed = False
    old_path = file_path
    new_path = file_path

    # Priority
    if priority is not None:
        new_text = _rewrite_frontmatter_field(new_text, "priority", priority)

    # Epic
    if epic is not None:
        if epic:
            new_text = _rewrite_frontmatter_field(new_text, "epic", f"[[{epic}]]")
        else:
            new_text = _rewrite_frontmatter_field(new_text, "epic", None)

    # Domain — may trigger a filename rename
    if domain is not None:
        new_text = _rewrite_frontmatter_field(new_text, "domain_tags", domain if domain else None)

    # Write frontmatter changes first
    if new_text != text:
        with open(file_path, "w") as f:
            f.write(new_text)

    # Rename file if domain changed (or appeared / disappeared)
    old_filename = os.path.basename(file_path)
    old_stem = old_filename.rsplit(".md", 1)[0]
    current_fm = plate_frontmatter(new_text)
    current_domain = current_fm.get("domain_tags", "")
    expected_filename = _build_filename(issue_id, orig_title, current_domain or None)
    if expected_filename != old_filename:
        dir_name = os.path.dirname(file_path)
        new_path = os.path.join(dir_name, expected_filename)
        if os.path.exists(new_path):
            print(f"Error: target filename already exists: {new_path}")
            sys.exit(1)

        git_root = find_git_root(vault_path)
        src_tracked = bool(git_root) and is_tracked(git_root, file_path)
        if git_root and src_tracked:
            rc, _, err = run_cmd(
                f"git mv {shlex.quote(file_path)} {shlex.quote(new_path)}", cwd=git_root)
            if rc != 0:
                print(f"[RVC] git mv failed ({err.strip()}); falling back to plain move.")
                src_tracked = False
        if not src_tracked:
            os.rename(file_path, new_path)

        # Heal wikilinks that pointed to the old filename stem
        _rewrite_wikilinks(vault_path, old_stem, expected_filename.rsplit(".md", 1)[0])

        if os.path.exists(context_cache_path(vault_path)):
            try:
                context_cache_repath(vault_path, old_path, new_path)
            except Exception:
                pass

        renamed = True
        file_path = new_path

    if priority is not None or epic is not None or domain is not None or renamed:
        sync_after(vault_path, [old_path, new_path],
                   f"rvc: Updated {issue_id} (set)", skip_ci=skip_ci)

    parts = []
    if domain is not None:
        parts.append(f"domain={domain or '(none)'}")
    if epic is not None:
        parts.append(f"epic={epic or '(none)'}")
    if priority is not None:
        parts.append(f"priority={priority}")
    if renamed:
        parts.append(f"renamed -> {os.path.basename(new_path)}")
    print(f"[RVC] Updated {issue_id}: {', '.join(parts)}")

    return new_path


def cmd_search(vault_path, query):
    """Search vault .md files: substring lines first, then an all-terms fallback.

    A multi-word query that matches nothing whole used to print a bare
    "No results" with no why (FEEDBACK-rvc 2026-11-05: `search "apostrophe
    filename"` found nothing while `search "apostrophe"` hit 3 — the file said
    "filenames"). Now: lines containing the whole phrase; else lines containing
    every term (substring, so "filename" still hits "filenames"); else a hint.
    """
    def _file_lines():
        for root, dirs, files in os.walk(vault_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue
                rel = os.path.relpath(fpath, vault_path)
                for i, line in enumerate(content.split("\n"), 1):
                    yield rel, i, line

    results = []
    for rel, i, line in _file_lines():
        if query.lower() in line.lower():
            results.append(f"{rel}:{i}: {line.strip()}")

    note = ""
    tokens = [t for t in query.split() if t]
    if not results and len(tokens) > 1:
        # Fallback: every term as a substring of the same line.
        low = [t.lower() for t in tokens]
        for rel, i, line in _file_lines():
            lline = line.lower()
            if all(t in lline for t in low):
                results.append(f"{rel}:{i}: {line.strip()}")
        if results:
            note = " (all-terms fallback: no line carries the whole phrase)"

    if results:
        print(f"# Search results for '{query}' ({len(results)} matches){note}\n")
        for r in results:
            print(r)
    else:
        print(f"No results for '{query}'")
        if len(tokens) > 1:
            print(f"      No line contains every term: {', '.join(tokens)}.")
            print("      Try fewer words — search matches lines, not whole files.")
        else:
            print("      Try a shorter fragment — search matches text inside lines.")
