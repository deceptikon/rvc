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

def find_file_by_id(vault_path, item_id):
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.startswith(item_id):
                return os.path.join(root, file)
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

    for link in links:
        link_name = link.split('|')[0]
        spec_path = None
        for root, dirs, files in os.walk(vault_path):
            for file in files:
                if file.replace(".md", "") == link_name or file == f"{link_name}.md":
                    spec_path = os.path.join(root, file)
                    break
            if spec_path: break

        if spec_path:
            print(f"--- REFERENCE: [[{link_name}]] ---")
            with open(spec_path, 'r') as f_spec:
                print(f_spec.read())
            print(f"\n--- END OF REFERENCE ---\n")
        else:
            print(f"--- REFERENCE [[{link_name}]] NOT FOUND IN VAULT ---\n")

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

    project_p = subparsers.add_parser("project")
    project_p.add_argument("action", choices=["init", "info"])
    project_p.add_argument("target_path", nargs="?")
    project_p.add_argument("--vault-name", default="vault",
                           help="Vault directory name (default: vault)")

    args = parser.parse_args()

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
