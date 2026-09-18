"""Issue lifecycle operations: creation, transitions, querying, and retrieval."""

import os
import sys
import re
import datetime

from rvc.core import (
    resolve_tree, tree_dirs, hot_dirs, state_label, run_cmd, find_git_root,
    find_file_by_id, vault_create_lock, _next_id, LEGACY_PRIORITY_TO_P, STATUS_ALIAS
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
            rc, _, err = run_cmd(f"git mv '{file_path}' '{new_file_path}'", cwd=git_root)
            if rc == 0:
                moved = True
            else:
                print(f"[RVC] git mv failed ({err.strip()}); falling back to plain move.")
        if not moved:
            if git_root and src_tracked:
                run_cmd(f"git rm -f '{file_path}'", cwd=git_root)
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


def cmd_create_issue(vault_path, title, prefix="STORY", issue_type="story",
                     priority="Medium", body="", directory=None,
                     epic="", extra_frontmatter=None, skip_ci=True):
    """Create a new issue file with proper frontmatter."""
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

    try:
        with vault_create_lock(vault_path):
            issue_id = _next_id(vault_path, prefix)
            safe_title = _sanitize_filename(title)
            filename = f"{issue_id}-{safe_title}.md"
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
    
    sync_after(vault_path, [filepath], f"rvc: Created issue {issue_id}: {title}", skip_ci=skip_ci)
    
    return filepath


def cmd_search(vault_path, query):
    """Search vault .md files for a pattern (case-insensitive grep)."""
    results = []
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(root, fname)
            try:
                content = open(fpath, "r").read()
                for i, line in enumerate(content.split("\n"), 1):
                    if query.lower() in line.lower():
                        rel = os.path.relpath(fpath, vault_path)
                        results.append(f"{rel}:{i}: {line.strip()}")
            except Exception:
                pass

    if results:
        print(f"# Search results for '{query}' ({len(results)} matches)\n")
        for r in results:
            print(r)
    else:
        print(f"No results for '{query}'")
