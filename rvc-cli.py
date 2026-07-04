#!/usr/bin/env python3
import os
import sys
import re
import argparse
import subprocess

def run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def _is_vault_dir(path):
    """Check if a path looks like an RVC vault (has 10_Issues + .obsidian)."""
    return (os.path.isdir(os.path.join(path, "10_Issues"))
            and os.path.isdir(os.path.join(path, ".obsidian")))


def find_vault_root(start_path):
    """Locate the vault root by checking (in order):
    1. A .rvc-root marker file (allows any directory name)
    2. A directory with RVC structure (10_Issues/ + .obsidian/)
    3. A directory literally named 'vault' (backward compat)
    """
    curr = os.path.abspath(start_path)
    max_depth = 8
    depth = 0
    while curr != os.path.dirname(curr) and depth < max_depth:
        depth += 1
        # 1. Check for .rvc-root marker in current directory
        if os.path.exists(os.path.join(curr, ".rvc-root")):
            return curr
        # 2. Check children for .rvc-root marker or RVC structure
        try:
            for entry in os.listdir(curr):
                child = os.path.join(curr, entry)
                if not os.path.isdir(child):
                    continue
                if os.path.isfile(os.path.join(child, ".rvc-root")):
                    return child
                if _is_vault_dir(child):
                    return child
        except PermissionError:
            break
        # 3. Backward compat: literal 'vault' directory
        vault_dir = os.path.join(curr, "vault")
        if os.path.isdir(vault_dir):
            return vault_dir
        if os.path.basename(curr) == "vault":
            return curr
        curr = os.path.dirname(curr)
    return None

def find_git_root(vault_path):
    curr = os.path.abspath(vault_path)
    while curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return None

def sync_before(vault_path):
    git_root = find_git_root(vault_path)
    if git_root:
        print("[RVC] Synchronizing state (git pull --rebase)...")
        rc, out, err = run_cmd("git pull --rebase", cwd=git_root)
        if rc != 0:
            print(f"[RVC] Warning: Git pull failed:\n{err}")

def sync_after(vault_path, file_paths, msg):
    git_root = find_git_root(vault_path)
    if git_root:
        print("[RVC] Committing and pushing state...")
        for fp in file_paths:
            run_cmd(f"git add '{fp}'", cwd=git_root)
        run_cmd(f"git commit -m '{msg}'", cwd=git_root)
        rc, out, err = run_cmd("git push", cwd=git_root)
        if rc != 0:
            print(f"[RVC] Warning: Git push failed:\n{err}")

def build_vault_index(vault_path):
    """Build an in-memory index of all files in the vault for O(1) lookups."""
    vault_index = {}
    for root, dirs, files in os.walk(vault_path):
        # Skip hidden directories (except .obsidian for structure)
        dirs[:] = [d for d in dirs if not d.startswith(".") or d == ".obsidian"]
        for file in files:
            # Remove .md extension and any anchors (#...) for indexing
            base_name = file.rsplit('.md', 1)[0]
            # Also support files without extensions
            if base_name not in vault_index:
                vault_index[base_name] = os.path.join(root, file)
    return vault_index

def find_file_by_id(vault_path, item_id):
    # Clean the item_id to remove any anchors
    clean_id = item_id.split('#')[0]
    
    # Build or reuse the vault index
    if not hasattr(find_file_by_id, '_vault_cache'):
        find_file_by_id._vault_cache = {}
    
    cache_key = vault_path
    if cache_key not in find_file_by_id._vault_cache:
        find_file_by_id._vault_cache[cache_key] = build_vault_index(vault_path)
    
    vault_index = find_file_by_id._vault_cache[cache_key]
    
    # Exact match first
    if clean_id in vault_index:
        return vault_index[clean_id]
    
    # Prefix match (e.g., item_id="STORY-05" matches "STORY-05-some-title")
    for filename in vault_index.keys():
        if filename.startswith(clean_id + "-"):
            return vault_index[filename]
    
    return None

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

def cmd_context(vault_path, item_id):
    file_path = find_file_by_id(vault_path, item_id)
    if not file_path:
        print(f"Error: Item {item_id} not found.")
        sys.exit(1)

    with open(file_path, 'r') as f:
        content = f.read()

    links = re.findall(r'\[\[(.*?)\]\]', content)
    
    print(f"# RVC Context Assembler: {item_id}\n")
    print(f"Found {len(links)} references. Gathering documentation...\n")

    # Build the vault index once for all link lookups
    vault_index = build_vault_index(vault_path)
    
    for link in links:
        # Strip anchor and alias to get base filename
        link_name = link.split('|')[0].split('#')[0]
        spec_path = None
        
        # Exact match first
        if link_name in vault_index:
            spec_path = vault_index[link_name]
        else:
            # Prefix match
            for filename in vault_index.keys():
                if filename.startswith(link_name + "-"):
                    spec_path = vault_index[filename]
                    break

        if spec_path:
            print(f"--- REFERENCE: [[{link}]] ---")
            print(f"File: {os.path.relpath(spec_path, vault_path)}\n")
            with open(spec_path, 'r') as f_spec:
                print(f_spec.read())
            print(f"\n--- END OF REFERENCE ---\n")
        else:
            print(f"--- REFERENCE [[{link}]] NOT FOUND IN VAULT ---\n")

def cmd_issue_action(vault_path, issue_id, action):
    valid_actions = {
        "start": {"status": "Active", "folder": "10_Issues/02_Active"},
        "review": {"status": "Review", "folder": "10_Issues/03_Review"},
        "done": {"status": "Done", "folder": "10_Issues/04_Done"},
    }
    if action not in valid_actions:
        print(f"Error: Invalid action '{action}'. Use start, review, or done.")
        sys.exit(1)

    sync_before(vault_path)

    file_path = find_file_by_id(vault_path, issue_id)
    if not file_path:
        print(f"Error: Item {issue_id} not found.")
        sys.exit(1)

    with open(file_path, 'r') as f:
        content = f.read()

    new_status = valid_actions[action]["status"]
    target_folder = os.path.join(vault_path, valid_actions[action]["folder"])
    os.makedirs(target_folder, exist_ok=True)

    new_content = re.sub(r'^status:\s*.*$', f"status: {new_status}", content, flags=re.MULTILINE)

    file_name = os.path.basename(file_path)
    new_file_path = os.path.join(target_folder, file_name)

    if os.path.abspath(file_path) != os.path.abspath(new_file_path):
        os.remove(file_path)
        git_root = find_git_root(vault_path)
        if git_root:
            run_cmd(f"git rm '{file_path}'", cwd=git_root)
    
    with open(new_file_path, 'w') as f:
        f.write(new_content)

    print(f"[RVC] Issue {issue_id} marked as {new_status} and moved to {valid_actions[action]['folder']}.")

    sync_after(vault_path, [file_path, new_file_path], f"rvc: Issue {issue_id} -> {new_status}")

def cmd_issue_list(vault_path, status):
    issues_dir = os.path.join(vault_path, "10_Issues")
    if not os.path.exists(issues_dir):
        print(f"Error: Issues directory not found at {issues_dir}")
        sys.exit(1)

    print(f"# RVC Issues List ({status or 'All'})")
    found_any = False
    for root, dirs, files in os.walk(issues_dir):
        for file in files:
            if not file.endswith(".md"): continue
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                content = f.read()
            match = re.search(r'^status:\s*(.*)$', content, flags=re.MULTILINE)
            file_status = match.group(1).strip() if match else "Unknown"
            
            if status and status.lower() not in file_status.lower():
                continue
                
            print(f"- {file} [{file_status}]")
            found_any = True
            
    if not found_any:
        print("No issues found.")

def _sanitize_filename(name):
    """Remove unsafe characters for filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "-")


def _next_id(vault_path, prefix="STORY"):
    """Find the next sequential ID for a given prefix (e.g., STORY-30)."""
    max_num = 0
    issues_dir = os.path.join(vault_path, "10_Issues")
    if not os.path.exists(issues_dir):
        return f"{prefix}-01"
    for root, dirs, files in os.walk(issues_dir):
        for f in files:
            m = re.match(rf'^{re.escape(prefix)}-(\d+)', f)
            if m:
                max_num = max(max_num, int(m.group(1)))
    width = max(2, len(str(max_num + 1)))
    return f"{prefix}-{str(max_num + 1).zfill(width)}"


def cmd_create_issue(vault_path, title, prefix="STORY", issue_type="story",
                     priority="Medium", body="", directory="01_To_Do",
                     epic="", extra_frontmatter=None):
    """Create a new issue file with proper frontmatter."""
    target_dir = os.path.join(vault_path, "10_Issues", directory)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    issue_id = _next_id(vault_path, prefix)
    safe_title = _sanitize_filename(title)
    filename = f"{issue_id}-{safe_title}.md"
    filepath = os.path.join(target_dir, filename)

    if os.path.exists(filepath):
        print(f"Error: File already exists: {filepath}")
        sys.exit(1)

    # Build YAML frontmatter
    import datetime
    today = datetime.date.today().isoformat()
    lines = [
        "---",
        f"type: {issue_type}",
        f"status: To Do",
        f"priority: {priority}",
    ]
    if epic:
        lines.append(f"epic: [[{epic}]]")
    lines.append(f"started: {today}")
    if extra_frontmatter:
        for k, v in extra_frontmatter.items():
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {issue_id}: {title}")
    lines.append("")
    if body:
        lines.append(body.replace("\\n", "\n"))
    else:
        lines.append("## Context")
        lines.append("")
        lines.append("## Acceptance Criteria")
        lines.append("- [ ] ")
        lines.append("")
        lines.append("## Test Case Requirements")

    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[RVC] Created {filename}")
    print(f"      {filepath}")
    print(f"      Hint: rvc issue {issue_id} start")
    return filepath


def _parse_gitmodules(repo_root):
    """Parse .gitmodules and return {path: url} for all submodules."""
    modules_path = os.path.join(repo_root, ".gitmodules")
    if not os.path.exists(modules_path):
        return {}
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read(modules_path)
    subs = {}
    for sec in cfg.sections():
        path = cfg.get(sec, "path", fallback=None)
        url = cfg.get(sec, "url", fallback=None)
        if path:
            subs[os.path.join(repo_root, path)] = url or ""
    return subs


def _find_dirty_submodules(repo_root):
    """Return list of submodule paths that have uncommitted changes."""
    subs = _parse_gitmodules(repo_root)
    dirty = []
    for path in subs:
        rc, out, err = run_cmd("git status --porcelain", cwd=path)
        if rc == 0 and out.strip():
            dirty.append(path)
    return dirty


def cmd_git_commit_all(vault_path, message, dry_run=False, no_push=False, push=False):
    """Commit across all dirty submodules, then in parent repo. Safe incremental.

    Exactly one of --dry-run, --no-push, or --push must be specified.
    Uses `git add -u` (tracked files only) — never stages untracked files.
    """
    if not dry_run and not no_push and not push:
        print("[git-commit-all] Error: Specify --dry-run, --no-push, or --push")
        sys.exit(1)

    git_root = find_git_root(vault_path)
    if not git_root:
        print("[git-commit-all] Error: No git root found.")
        sys.exit(1)

    dirty = _find_dirty_submodules(git_root)

    if not dirty:
        print("[git-commit-all] No dirty submodules found.")
        return

    print(f"[git-commit-all] Dirty submodules ({len(dirty)}):")
    for d in dirty:
        rel = os.path.relpath(d, git_root)
        rc, out, err = run_cmd("git diff --stat", cwd=d)
        diff_out = out.strip()
        print(f"  - {rel}:")
        if diff_out:
            for line in diff_out.split("\n"):
                print(f"      {line}")
        else:
            print(f"      (unstaged changes — see `git status`)")
        if dry_run:
            print(f"      → Would: git add -u && git commit -m '{message}'"
                  + (" && git push" if push else ""))

    if dry_run:
        print("\n[git-commit-all] Dry-run complete. No changes made.")
        return

    for sub_path in dirty:
        rel = os.path.relpath(sub_path, git_root)
        print(f"\n[git-commit-all] Committing in {rel}...")
        rc1, _, err1 = run_cmd("git add -u", cwd=sub_path)
        if rc1 != 0:
            print(f"[git-commit-all] FAILED: git add in {rel}:\n{err1}")
            sys.exit(1)
        rc2, _, err2 = run_cmd(f"git commit -m '{message}'", cwd=sub_path)
        if rc2 != 0:
            print(f"[git-commit-all] FAILED: git commit in {rel}:\n{err2}")
            sys.exit(1)
        if push:
            rc3, _, err3 = run_cmd("git push", cwd=sub_path)
            if rc3 != 0:
                print(f"[git-commit-all] WARNING: git push failed in {rel}:\n{err3}")
        else:
            print(f"[git-commit-all]   Committed (no push). Use --push to push.")

    print(f"\n[git-commit-all] Committing in parent repo...")
    rc1, _, err1 = run_cmd("git add -u", cwd=git_root)
    if rc1 != 0:
        print(f"[git-commit-all] FAILED: git add in parent:\n{err1}")
        sys.exit(1)
    rc2, out2, err2 = run_cmd(f"git commit -m '{message}'", cwd=git_root)
    if rc2 != 0:
        print(f"[git-commit-all] Parent commit skipped — nothing to commit?")
        print(f"  stdout: {out2.strip()}\n  stderr: {err2.strip()}")
    if push:
        rc3, _, err3 = run_cmd("git push", cwd=git_root)
        if rc3 != 0:
            print(f"[git-commit-all] WARNING: git push failed in parent:\n{err3}")
    else:
        print(f"[git-commit-all]   Committed (no push). Use --push to push.")

    print("[git-commit-all] Done.")


def cmd_search(vault_path, query):
    """Search vault .md files for a pattern (case-insensitive grep)."""
    results = []
    for root, dirs, files in os.walk(vault_path):
        # Skip hidden dirs except .obsidian for structure
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


def main():
    parser = argparse.ArgumentParser(description="RVC CLI - Vault Context Interface")
    parser.add_argument("--path", default=".", help="Path to project or vault")
    subparsers = parser.add_subparsers(dest="command")

    get_p = subparsers.add_parser("get")
    get_p.add_argument("id")

    context_p = subparsers.add_parser("context")
    context_p.add_argument("id")

    issue_p = subparsers.add_parser("issue")
    issue_p.add_argument("action_or_id")
    issue_p.add_argument("action_or_status", nargs="?")

    create_p = subparsers.add_parser("create", help="Create a new issue")
    create_p.add_argument("title", help="Issue title")
    create_p.add_argument("--prefix", default="STORY", help="ID prefix (default: STORY)")
    create_p.add_argument("--type", default="story", dest="issue_type",
                          choices=["story", "bug", "task", "epic"],
                          help="Issue type (default: story)")
    create_p.add_argument("--priority", default="Medium",
                          choices=["Low", "Medium", "High", "Critical"],
                          help="Priority (default: Medium)")
    create_p.add_argument("--body", default="", help="Initial issue body text")
    create_p.add_argument("--dir", default="01_To_Do", dest="directory",
                          help="Target folder (default: 01_To_Do)")
    create_p.add_argument("--epic", default="", help="Parent epic name (e.g. EPIC-05-PRD-Phase-2)")

    search_p = subparsers.add_parser("search", help="Search vault files")
    search_p.add_argument("query", help="Search query (case-insensitive)")

    commit_p = subparsers.add_parser("git-commit-all", help="Commit across all dirty submodules + parent repo (safe incremental)")
    commit_p.add_argument("message", help="Commit message (e.g. 'feat: something (STORY-XX)')")
    commit_p.add_argument("--dry-run", action="store_true", help="Show plan without making changes")
    commit_p.add_argument("--no-push", action="store_true", help="Commit but do not push")
    commit_p.add_argument("--push", action="store_true", help="Commit and push (opt-in)")

    rescan_p = subparsers.add_parser("rescan", help="Rescan vault: fix frontmatter, add wikilinks")
    rescan_p.add_argument("--dry-run", action="store_true", help="Show what would change without writing")

    init_p = subparsers.add_parser("init", help="Initialize a new vault (flat — no vault/ subdirectory)")
    init_p.add_argument("target_path", nargs="?", default=".", help="Directory to initialize (default: current)")

    project_p = subparsers.add_parser("project")
    project_p.add_argument("action", choices=["init", "info"])
    project_p.add_argument("target_path", nargs="?")
    project_p.add_argument("--vault-name", default="vault",
                           help="Vault directory name (default: vault)")

    args = parser.parse_args()

    if args.command == "init":
        target = args.target_path or "."
        vault_dir = os.path.abspath(target)
        os.makedirs(os.path.join(vault_dir, "00_Project"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "00_Backlog"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "01_To_Do"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "02_Active"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "03_Review"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "04_Done"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "20_Specs"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "90_Assets"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "99_Archive"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, ".obsidian"), exist_ok=True)

        with open(os.path.join(vault_dir, ".rvc-root"), "w") as f:
            f.write("# RVC vault root\n")

        with open(os.path.join(vault_dir, "00_Project", "REGLAMENT.md"), "w") as f:
            f.write("# ProjectReglament\n")
        print(f"[RVC] Initialized vault structure at {vault_dir}")
        print(f"[RVC] Marker file: {vault_dir}/.rvc-root")
        print(f"[RVC] Tip: open this directory directly in Obsidian (no vault/ subfolder)")
        return

    if args.command == "project" and args.action == "init":
        target = args.target_path or "."
        vault_name = args.vault_name
        vault_dir = os.path.join(os.path.abspath(target), vault_name)
        os.makedirs(os.path.join(vault_dir, "00_Project"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "00_Backlog"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "01_To_Do"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "02_Active"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "03_Review"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "04_Done"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "20_Specs"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "90_Assets"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "99_Archive"), exist_ok=True)

        # Write .rvc-root marker
        with open(os.path.join(vault_dir, ".rvc-root"), "w") as f:
            f.write(f"vault={vault_name}\n")

        with open(os.path.join(vault_dir, "00_Project", "REGLAMENT.md"), "w") as f:
            f.write("# ProjectReglament\n")
        print(f"[RVC] Initialized vault structure at {vault_dir}")
        print(f"[RVC] Marker file: {vault_dir}/.rvc-root")
        if vault_name != "vault":
            print(f"[RVC] Custom vault name: '{vault_name}' — open this path in Obsidian")
        return

    vault_root = find_vault_root(args.path)
    if not vault_root:
        print("Error: Could not find a 'vault' directory in this path or its parents.")
        sys.exit(1)

    if args.command == "get":
        cmd_get(vault_root, args.id)
    elif args.command == "context":
        cmd_context(vault_root, args.id)
    elif args.command == "issue":
        if args.action_or_id == "list":
            cmd_issue_list(vault_root, args.action_or_status)
        else:
            if not args.action_or_status:
                cmd_get(vault_root, args.action_or_id)
            else:
                cmd_issue_action(vault_root, args.action_or_id, args.action_or_status)
    elif args.command == "create":
        cmd_create_issue(
            vault_root,
            title=args.title,
            prefix=args.prefix,
            issue_type=args.issue_type,
            priority=args.priority,
            body=args.body,
            directory=args.directory,
            epic=args.epic,
        )
    elif args.command == "search":
        cmd_search(vault_root, args.query)
    elif args.command == "rescan":
        script_dir = os.path.dirname(os.path.realpath(__file__))
        restructure_script = os.path.join(script_dir, "vault-restructure.py")
        cmd = ["python3", restructure_script, vault_root]
        if getattr(args, "dry_run", False):
            cmd.append("--dry-run")

        rc, out, err = run_cmd(" ".join(cmd))
        print(out)
        if err:
            print(f"[rescan] stderr: {err}", file=sys.stderr)
    elif args.command == "git-commit-all":
        cmd_git_commit_all(vault_root, args.message,
                           dry_run=getattr(args, "dry_run", False),
                           no_push=getattr(args, "no_push", False),
                           push=getattr(args, "push", False))
    elif args.command == "project" and args.action == "info":
        print(f"# Vault Info")
        print(f"  Path: {vault_root}")
        print(f"  Name: {os.path.basename(vault_root)}")
        roadmap = os.path.join(vault_root, "00_Project", "ROADMAP.md")
        if os.path.exists(roadmap):
            print(f"\n--- ROADMAP.md ---")
            with open(roadmap, 'r') as f:
                print(f.read())
        else:
            print("  ROADMAP.md: not found")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
