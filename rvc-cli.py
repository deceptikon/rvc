#!/usr/bin/env python3
import os
import sys
import re
import argparse
import subprocess

def run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def find_vault_root(start_path):
    curr = os.path.abspath(start_path)
    while curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "vault")):
            return os.path.join(curr, "vault")
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

    project_p = subparsers.add_parser("project")
    project_p.add_argument("action", choices=["init", "info"])
    project_p.add_argument("target_path", nargs="?")

    args = parser.parse_args()
    
    if args.command == "project" and args.action == "init":
        target = args.target_path or "."
        vault_dir = os.path.join(target, "vault")
        os.makedirs(os.path.join(vault_dir, "00_Project"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "00_Backlog"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "01_To_Do"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "02_Active"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "03_Review"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "10_Issues", "04_Done"), exist_ok=True)
        os.makedirs(os.path.join(vault_dir, "20_Specs"), exist_ok=True)
        
        with open(os.path.join(vault_dir, "00_Project", "REGLAMENT.md"), "w") as f:
            f.write("# ProjectReglament\n")
        print(f"[RVC] Initialized vault structure at {vault_dir}")
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
    elif args.command == "project" and args.action == "info":
        roadmap = os.path.join(vault_root, "00_Project", "ROADMAP.md")
        if os.path.exists(roadmap):
            with open(roadmap, 'r') as f:
                print(f.read())
        else:
            print("ROADMAP.md not found.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
