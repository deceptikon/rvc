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

# ── Per-vault tree config (STORY-105) ────────────────────────────────────────
# .rvc-root may carry `tree.<verb>=<dir>` lines. Absent them, LEGACY_TREE applies,
# so unconfigured vaults (TEAMFLOW, conductor, dash fixtures) keep their tree.

LEGACY_TREE = {
    "create": "10_Issues/01_To_Do",
    "triage": "10_Issues/01_To_Do",
    "start": "10_Issues/02_Active",
    "review": "10_Issues/03_Review",
    "done": "10_Issues/04_Done",
    "defer": "10_Issues/00_Backlog",
    "evict": "99_Archive",
    "supersede": "99_Archive",
    "roadmap": "00_Project",
}

NEWVAULT_TREE = {
    "create": "00_INBOX",
    "triage": "20_NEXT",
    "start": "30_ACTIVE",
    "block": "40_DECIDE",
    "defer": "50_DEFERRED",
    "review": "60_DONE",
    "done": "60_DONE",
    "evict": "90_ARCHIVE/done",
    "supersede": "90_ARCHIVE/superseded",
    "roadmap": "10_CONTEXT",
}

# Legacy status-name → verb. Folder = state, but the MCP contract and old muscle
# memory still speak status strings ("To Do", "Review"…). Resolve them to verbs,
# then verbs to dirs through the vault's tree.
STATUS_ALIAS = {
    "inbox": "create",
    "todo": "triage",
    "to do": "triage",
    "to_do": "triage",
    "next": "triage",
    "backlog": "defer",
    "deferred": "defer",
    "active": "start",
    "working": "start",
    "developing": "start",
    "decide": "block",
    "blocked": "block",
    "review": "review",
    "done": "done",
    "closed": "done",
    "evict": "evict",
    "archive": "evict",
    "superseded": "supersede",
}

# Buckets that show in a bare `rvc issue list` (no filter) — hot states only;
# archive/evict listings are opt-in via a verb or --dir.
HOT_BUCKET_VERBS = {"create", "triage", "start", "block", "defer", "review", "done"}

LEGACY_STATE_LABEL = {
    "00_Backlog": "Backlog",
    "01_To_Do": "To Do",
    "02_Active": "Active",
    "03_Review": "Review",
    "04_Done": "Done",
}


def read_tree_config(vault_path):
    """Read `tree.<verb>=<dir>` lines from .rvc-root. {} if none (→ legacy)."""
    root_file = os.path.join(vault_path, ".rvc-root")
    tree = {}
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("tree.") and "=" in line:
                    key, _, val = line.partition("=")
                    tree[key[len("tree."):].strip()] = val.strip()
    return tree


def resolve_tree(vault_path, preset=None):
    """Effective verb→dir map: vault config, else a preset, else the legacy map."""
    if preset:
        return dict(preset)
    return read_tree_config(vault_path) or dict(LEGACY_TREE)


def tree_dirs(tree):
    """All distinct directories in a resolved tree (sorted, stable)."""
    return sorted({d for d in tree.values() if d})


def hot_dirs(tree):
    """Directories for the default, unfiltered issue list (excludes archives)."""
    return sorted({tree[v] for v in HOT_BUCKET_VERBS if v in tree})


def state_label(file_path, vault_path):
    """Derive the issue state from its parent folder — never frontmatter."""
    parent = os.path.basename(os.path.dirname(file_path))
    return LEGACY_STATE_LABEL.get(parent, parent)


def write_tree_config(vault_path, tree):
    """(Re)write .rvc-root with a tree.* block, preserving a leading vault= line."""
    root_file = os.path.join(vault_path, ".rvc-root")
    keep = []
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("tree.") or not line:
                    continue
                keep.append(line)
    with open(root_file, "w") as f:
        f.write("# RVC vault root\n")
        for line in keep:
            f.write(line + "\n")
        for verb, d in sorted(tree.items()):
            f.write(f"tree.{verb}={d}\n")

# Generic project README, copied to the ROOT of whichever project gets RVC-fied
# by `init` / `project init`. Placeholders: {PROJECT_NAME} {VAULT} {ROUTING} {CONTEXT}.
README_TEMPLATE = """# {PROJECT_NAME}

Managed with **RVC** — a lightweight, folder-as-state issue & knowledge vault at `{VAULT}/`.

> **State lives in folders, not frontmatter.** Where an issue file sits *is* its status.
> **Context lives in the vault, not this file.** Everything an agent or developer needs starts
> at the vault's single context file — `{VAULT}/{ROUTING}`. The root
> `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`/`QWEN.md` are symlinks to it.

## Where to look next

| Path | What it is |
|------|-----------|
| `{VAULT}/{ROUTING}` | The constitution — bucket law, triage rules, session protocol (canonical) |
| `{VAULT}/.rvc-root` | Vault marker + `tree.<verb>=<dir>` map for this vault |
| `{VAULT}/{CONTEXT}/DECISIONS.md` | Architectural decisions and their rationale |
| `{VAULT}/{CONTEXT}/GOTCHAS.md` | Non-obvious bugs and environment traps |
| `{VAULT}/{CONTEXT}/STATE.json` | Current active issue / session state |
| `{VAULT}/` | Lifecycle buckets (new vaults: 00_INBOX … 90_ARCHIVE; legacy: 10_Issues) |

## Commands

Run from anywhere in the project — the vault is auto-detected.

```bash
rvc issue list              # everything open
rvc create "First"          # idea → inbox
rvc issue STORY-01 start    # → active (a git mv under the hood)
rvc context STORY-01        # pull linked context
rvc issue STORY-01 done     # → done
```

Transitions are plain `git mv`, so every move is recoverable through git history.

## Protocol

Read `{VAULT}/{ROUTING}` first — it overrides the rest of this file.
"""

# Harness-read context files at the project root: symlinks onto the vault's
# constitution, so there is exactly one canonical context file per project.
CONTEXT_LINK_NAMES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "QWEN.md")


def _link_context_roots(project_root, vault_rel, routing_rel):
    """Symlink root AGENTS.md/CLAUDE.md/GEMINI.md/QWEN.md -> <vault>/<constitution>.

    Relative link bodies so the project stays portable (copy, mount, worktree).
    Idempotent; re-points links that already exist. A real file with one of these
    names is never clobbered — it is project content, not ours to replace.
    """
    target_rel = os.path.normpath(os.path.join(vault_rel, routing_rel))
    want = os.path.realpath(os.path.join(project_root, target_rel))
    for name in CONTEXT_LINK_NAMES:
        link = os.path.join(project_root, name)
        if os.path.lexists(link) and not os.path.islink(link):
            print(f"[RVC] Keeping existing {name} (real file, not a symlink) — not linking")
            continue
        if os.path.islink(link):
            if os.path.realpath(link) == want:
                print(f"[RVC] Already linked: {name} -> {target_rel}")
                continue
            os.remove(link)
        os.symlink(target_rel, link)
        print(f"[RVC] Linked {name} -> {target_rel}")


def _write_project_readme(project_root, project_name, vault_rel, tree_preset):
    """Render README_TEMPLATE and drop it at the project root. Never overwrites an
    existing README.md (the project may already have one)."""
    readme = os.path.join(project_root, "README.md")
    if os.path.exists(readme):
        print(f"[RVC] Skipping README.md — already exists at {readme}")
        return
    if tree_preset == "newvault":
        routing, ctx = "10_CONTEXT/ROUTING.md", "10_CONTEXT"
    else:
        routing, ctx = "00_Project/REGLAMENT.md", "00_Project"
    body = README_TEMPLATE.replace("{PROJECT_NAME}", project_name)
    body = body.replace("{VAULT}", vault_rel)
    body = body.replace("{ROUTING}", routing)
    body = body.replace("{CONTEXT}", ctx)
    # Any leftover placeholder means the template drifted — refuse to ship it.
    if "{" in body and "}" in body:
        raise ValueError(f"README_TEMPLATE placeholder not replaced: {body[body.index('{'):body.index('}') + 1]}")
    with open(readme, "w") as f:
        f.write(body)
    print(f"[RVC] Wrote project README: {readme}")

def cmd_init(target_path=".", tree="legacy"):
    """Scaffold a new RVC vault directly in target_path (flat — no vault/ subdir)."""
    vault_dir = os.path.abspath(target_path)
    newvault = tree == "newvault"
    if newvault:
        t = dict(NEWVAULT_TREE)
        init_dirs = tree_dirs(t) + [".obsidian"]
    else:
        t = dict(LEGACY_TREE)
        init_dirs = [
            "00_Project",
            "10_Issues/00_Backlog", "10_Issues/01_To_Do",
            "10_Issues/02_Active", "10_Issues/03_Review", "10_Issues/04_Done",
            "20_Specs", "90_Assets", "99_Archive", ".obsidian",
        ]
    for d in init_dirs:
        os.makedirs(os.path.join(vault_dir, d), exist_ok=True)

    with open(os.path.join(vault_dir, ".rvc-root"), "w") as f:
        f.write("# RVC vault root\n")
        if newvault:
            for verb, d in sorted(t.items()):
                f.write(f"tree.{verb}={d}\n")

    reglament = "10_CONTEXT/ROUTING.md" if newvault else "00_Project/REGLAMENT.md"
    routing_path = os.path.join(vault_dir, reglament)
    if os.path.exists(routing_path):
        print(f"[RVC] Keeping existing {reglament} (re-run is non-destructive)")
    else:
        with open(routing_path, "w") as f:
            f.write("# Vault Routing\n")
    _link_context_roots(vault_dir, ".", reglament)
    _write_project_readme(vault_dir, os.path.basename(vault_dir), ".", "newvault" if newvault else "legacy")
    print(f"[RVC] Initialized {'newvault' if newvault else 'legacy'} vault structure at {vault_dir}")
    print(f"[RVC] Marker file: {vault_dir}/.rvc-root")
    print(f"[RVC] Tip: open this directory directly in Obsidian (no vault/ subfolder)")
    return vault_dir

def cmd_project_init(target_path=".", vault_name="vault", tree="legacy"):
    """Scaffold a project: <target>/<vault_name>/ vault + README at the project root."""
    target = os.path.abspath(target_path)
    vault_dir = os.path.join(target, vault_name)
    newvault = tree == "newvault"
    if newvault:
        t = dict(NEWVAULT_TREE)
        init_dirs = tree_dirs(t)
    else:
        t = dict(LEGACY_TREE)
        init_dirs = [
            "00_Project",
            "10_Issues/00_Backlog", "10_Issues/01_To_Do",
            "10_Issues/02_Active", "10_Issues/03_Review", "10_Issues/04_Done",
            "20_Specs", "90_Assets", "99_Archive",
        ]
    for d in init_dirs:
        os.makedirs(os.path.join(vault_dir, d), exist_ok=True)

    with open(os.path.join(vault_dir, ".rvc-root"), "w") as f:
        f.write(f"vault={vault_name}\n")
        if newvault:
            for verb, d in sorted(t.items()):
                f.write(f"tree.{verb}={d}\n")

    reglament = "10_CONTEXT/ROUTING.md" if newvault else "00_Project/REGLAMENT.md"
    routing_path = os.path.join(vault_dir, reglament)
    if os.path.exists(routing_path):
        print(f"[RVC] Keeping existing {reglament} (re-run is non-destructive)")
    else:
        with open(routing_path, "w") as f:
            f.write("# Vault Routing\n")
    _link_context_roots(target, vault_name, reglament)
    _write_project_readme(target, os.path.basename(target), vault_name, "newvault" if newvault else "legacy")
    print(f"[RVC] Initialized {'newvault' if newvault else 'legacy'} vault structure at {vault_dir}")
    print(f"[RVC] Marker file: {vault_dir}/.rvc-root")
    if vault_name != "vault":
        print(f"[RVC] Custom vault name: '{vault_name}' — open this path in Obsidian")
    return vault_dir

def cmd_install(install_dir=None, force=False, check=False):
    """Install: symlink this script as `rvc` on PATH (default ~/.local/bin).

    Idempotent — a second run verifies and returns 0. --check verifies only.
    Refuses to clobber an existing unrelated file unless --force.
    """
    install_dir = install_dir or os.path.expanduser("~/.local/bin")
    source = os.path.realpath(__file__)
    target = os.path.join(install_dir, "rvc")

    if check:
        if os.path.islink(target) and os.path.realpath(target) == source:
            print(f"OK: {target} -> {source}")
            return 0
        print(f"NOT INSTALLED: {target} -> {source}")
        return 1

    if os.path.lexists(target):
        if os.path.islink(target) and os.path.realpath(target) == source:
            print(f"Already installed: {target} -> {source}")
            return 0
        if not force:
            print(f"Refusing to overwrite {target} (not this rvc). Pass --force to override.",
                  file=sys.stderr)
            return 1

    os.makedirs(install_dir, exist_ok=True)
    try:
        os.symlink(source, target)
    except FileExistsError:
        os.remove(target)
        os.symlink(source, target)
    print(f"Installed: {target} -> {source}")
    print("Install dir must be on PATH. Next: `rvc project init <dir>` to RVC-fy a project.")
    return 0

def sync_before(vault_path):
    git_root = find_git_root(vault_path)
    if git_root:
        print("[RVC] Synchronizing state (git pull --rebase)...")
        rc, out, err = run_cmd("git pull --rebase", cwd=git_root)
        if rc != 0:
            print(f"[RVC] Warning: Git pull failed:\n{err}")

def _push_enabled(vault_path):
    """Push is OPT-IN. Enabled only by env `RVC_PUSH=1` or `.rvc-root` line `push=true`.
    Prevents silent, unprompted git push from sync_after (review finding: auto-push
    synced origin/main without review)."""
    if os.environ.get("RVC_PUSH", "").strip() == "1":
        return True
    root_file = os.path.join(vault_path, ".rvc-root")
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("push=") and line[len("push="):].strip().lower() == "true":
                    return True
    return False

def sync_after(vault_path, file_paths, msg):
    git_root = find_git_root(vault_path)
    if git_root:
        print("[RVC] Committing state...")
        for fp in file_paths:
            run_cmd(f"git add '{fp}'", cwd=git_root)
        run_cmd(f"git commit -m '{msg}'", cwd=git_root)
        if _push_enabled(vault_path):
            rc, out, err = run_cmd("git push", cwd=git_root)
            if rc != 0:
                print(f"[RVC] Warning: Git push failed:\n{err}")
        else:
            print("[RVC] Skipping push (opt-in: RVC_PUSH=1 env or `push=true` in .rvc-root)")

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
    vault_index = build_vault_index(vault_path)
    
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
    tree = resolve_tree(vault_path)
    if action not in tree:
        print(f"Error: invalid action '{action}' for this vault's tree.")
        print(f"        Valid actions: {', '.join(sorted(tree.keys()))}")
        sys.exit(1)

    sync_before(vault_path)

    file_path = find_file_by_id(vault_path, issue_id)
    if not file_path:
        print(f"Error: Item {issue_id} not found.")
        sys.exit(1)

    target_rel = tree[action]
    target_folder = os.path.join(vault_path, target_rel)
    os.makedirs(target_folder, exist_ok=True)

    file_name = os.path.basename(file_path)
    new_file_path = os.path.join(target_folder, file_name)

    if os.path.abspath(file_path) != os.path.abspath(new_file_path):
        moved = False
        git_root = find_git_root(vault_path)
        if git_root:
            rc, _, err = run_cmd(f"git mv '{file_path}' '{new_file_path}'", cwd=git_root)
            if rc == 0:
                moved = True
            else:
                print(f"[RVC] git mv failed ({err.strip()}); falling back to plain move.")
        if not moved:
            if git_root:
                run_cmd(f"git rm -f '{file_path}'", cwd=git_root)
            os.rename(file_path, new_file_path)

    label = state_label(new_file_path, vault_path)
    print(f"[RVC] Issue {issue_id} moved to {label} ({target_rel}).")

    sync_after(vault_path, [file_path, new_file_path], f"rvc: Issue {issue_id} -> {label}")

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


def _next_id(vault_path, prefix="STORY"):
    """Find the next sequential ID for a given prefix (e.g., STORY-30)."""
    max_num = 0
    tree = resolve_tree(vault_path)
    for d in tree_dirs(tree):
        root = os.path.join(vault_path, d)
        if not os.path.isdir(root):
            continue
        for _, _, files in os.walk(root):
            for f in files:
                m = re.match(rf'^{re.escape(prefix)}-(\d+)', f)
                if m:
                    max_num = max(max_num, int(m.group(1)))
    if max_num == 0:
        return f"{prefix}-01"
    width = max(2, len(str(max_num + 1)))
    return f"{prefix}-{str(max_num + 1).zfill(width)}"


def cmd_create_issue(vault_path, title, prefix="STORY", issue_type="story",
                     priority="Medium", body="", directory=None,
                     epic="", extra_frontmatter=None):
    """Create a new issue file with proper frontmatter."""
    tree = resolve_tree(vault_path)
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

    issue_id = _next_id(vault_path, prefix)
    safe_title = _sanitize_filename(title)
    filename = f"{issue_id}-{safe_title}.md"
    filepath = os.path.join(target_dir, filename)

    if os.path.exists(filepath):
        print(f"Error: File already exists: {filepath}")
        sys.exit(1)

    # Build YAML frontmatter (no status — folder = state)
    import datetime
    today = datetime.date.today().isoformat()
    lines = [
        "---",
        f"type: {issue_type}",
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
    create_bucket = tree.get("create")
    hint_action = "triage" if (create_bucket and directory == create_bucket
                               and create_bucket != tree.get("triage")) else "start"
    print(f"      Hint: rvc issue {issue_id} {hint_action}")
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


def _ensure_on_branch(repo_path, label=""):
    """If HEAD is detached in a submodule, move to the default branch."""
    rc, out, _ = run_cmd("git symbolic-ref -q HEAD", cwd=repo_path)
    if rc == 0:
        return  # already on a branch
    for branch in ["main", "master"]:
        rc2, _, _ = run_cmd(f"git show-ref --verify refs/heads/{branch}", cwd=repo_path)
        if rc2 == 0:
            run_cmd(f"git checkout -B {branch} HEAD", cwd=repo_path)
            print(f"[git-commit-all]   {label}Moved detached HEAD to branch '{branch}'")
            return
    run_cmd("git checkout -b main", cwd=repo_path)
    print(f"[git-commit-all]   {label}Created branch 'main' at detached HEAD")


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

    # Check parent repo for staged/unstaged changes (before submodule commits)
    rc_ps, out_ps, _ = run_cmd("git diff --cached --stat", cwd=git_root)
    rc_pu, out_pu, _ = run_cmd("git diff --stat", cwd=git_root)
    parent_staged = out_ps.strip()
    parent_unstaged = out_pu.strip()
    has_parent_changes = bool(parent_staged or parent_unstaged)

    if not dirty and not has_parent_changes:
        print("[git-commit-all] Nothing to do — no dirty submodules and no parent changes.")
        return

    if not dirty:
        print("[git-commit-all] No dirty submodules found.")
    else:
        print(f"[git-commit-all] Dirty submodules ({len(dirty)}):")
        for d in dirty:
            rel = os.path.relpath(d, git_root)
            rc_staged, out_staged, _ = run_cmd("git diff --cached --stat", cwd=d)
            rc_unstaged, out_unstaged, _ = run_cmd("git diff --stat", cwd=d)
            rc_untracked, out_untracked, _ = run_cmd("git ls-files --others --exclude-standard", cwd=d)
            staged = out_staged.strip()
            unstaged = out_unstaged.strip()
            untracked = out_untracked.strip()
            print(f"  - {rel}:")
            if staged:
                for line in staged.split("\n"):
                    print(f"      staged: {line}")
            if unstaged:
                for line in unstaged.split("\n"):
                    print(f"      unstaged: {line}")
            if untracked:
                print(f"      untracked: {len(untracked.split(chr(10)))} file(s)")
            if not staged and not unstaged and not untracked:
                print(f"      (modified submodule pointer)")
            if dry_run:
                print(f"      → Would: git add -u && git commit -m '{message}'"
                      + (" && git push" if push else ""))

        if not dry_run:
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
                _ensure_on_branch(sub_path, label=f"{rel}: ")
                if push:
                    rc3, _, err3 = run_cmd("git push", cwd=sub_path)
                    if rc3 != 0:
                        print(f"[git-commit-all] WARNING: git push failed in {rel}:\n{err3}")
                else:
                    print(f"[git-commit-all]   Committed (no push). Use --push to push.")
            # Submodule commits changed parent refs — force parent processing
            has_parent_changes = True
            parent_staged = ""  # re-read parent state below
            parent_unstaged = ""

    # --- Parent repo section ---
    if dry_run:
        if not dirty and not has_parent_changes:
            return
        rc_ps2, out_ps2, _ = run_cmd("git diff --cached --stat", cwd=git_root)
        rc_pu2, out_pu2, _ = run_cmd("git diff --stat", cwd=git_root)
        pst = out_ps2.strip()
        pun = out_pu2.strip()
        if has_parent_changes and not (pst or pun):
            # Parent had initial changes that submodule commits might have consumed
            pst = parent_staged
            pun = parent_unstaged
        if pst or pun:
            print(f"\n[git-commit-all] Parent repo changes:")
            if pst:
                for line in pst.split("\n"):
                    print(f"      staged: {line}")
            if pun:
                for line in pun.split("\n"):
                    print(f"      unstaged: {line}")
            print(f"      → Would: git add -u && git commit -m '{message}'"
                  + (" && git push" if push else ""))
        print("\n[git-commit-all] Dry-run complete. No changes made.")
        return

    if has_parent_changes or dirty:
        print(f"\n[git-commit-all] Committing in parent repo...")
        rc1, _, err1 = run_cmd("git add -u", cwd=git_root)
        if rc1 != 0:
            print(f"[git-commit-all] FAILED: git add in parent:\n{err1}")
            sys.exit(1)
        rc2, out2, err2 = run_cmd(f"git commit -m '{message}'", cwd=git_root)
        if rc2 != 0:
            print(f"[git-commit-all] Parent commit skipped — nothing to commit?")
            print(f"  stdout: {out2.strip()}\n  stderr: {err2.strip()}")
        _ensure_on_branch(git_root, label="parent: ")
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
    issue_p.add_argument("--dir", dest="list_dir", default=None,
                         help="List a specific configured bucket (e.g. --dir 30_ACTIVE)")

    list_p = subparsers.add_parser("list", help="List issues (alias for `issue list`)")
    list_p.add_argument("status", nargs="?", default=None)
    list_p.add_argument("--dir", dest="list_dir", default=None,
                        help="List a specific configured bucket (e.g. --dir 20_NEXT)")

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
    create_p.add_argument("--dir", default=None, dest="directory",
                          help="Bucket for the new issue (default: this vault's inbox/triage bucket)")
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
    init_p.add_argument("--tree", choices=["legacy", "newvault"], default="legacy",
                        help="Vault tree preset (default: legacy)")

    project_p = subparsers.add_parser("project")
    project_p.add_argument("action", choices=["init", "info"])
    project_p.add_argument("target_path", nargs="?")
    project_p.add_argument("--vault-name", default="vault",
                           help="Vault directory name (default: vault)")
    project_p.add_argument("--tree", choices=["legacy", "newvault"], default="legacy",
                           help="Vault tree preset (default: legacy)")

    install_p = subparsers.add_parser(
        "install",
        help="Install this script as `rvc` on PATH (symlink to ~/.local/bin/rvc)")
    install_p.add_argument("--dir", default=None,
                           help="Install directory (default: ~/.local/bin)")
    install_p.add_argument("--force", action="store_true",
                           help="Overwrite an existing unrelated file at the target")
    install_p.add_argument("--check", action="store_true",
                           help="Verify installation and exit (no changes)")

    args = parser.parse_args()

    if args.command == "install":
        sys.exit(cmd_install(args.dir, force=args.force, check=args.check))

    if args.command == "init":
        cmd_init(args.target_path or ".", args.tree)
        return

    if args.command == "project" and args.action == "init":
        cmd_project_init(args.target_path or ".", args.vault_name, args.tree)
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
            cmd_issue_list(vault_root, args.action_or_status, list_dir=args.list_dir)
        else:
            if not args.action_or_status:
                cmd_get(vault_root, args.action_or_id)
            else:
                cmd_issue_action(vault_root, args.action_or_id, args.action_or_status)
    elif args.command == "list":
        cmd_issue_list(vault_root, args.status, list_dir=args.list_dir)
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
        tree = resolve_tree(vault_root)
        roadmap = os.path.join(vault_root, tree.get("roadmap", "00_Project"), "ROADMAP.md")
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
