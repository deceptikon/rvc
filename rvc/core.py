"""Core vault models, paths, process locking, and tree definitions."""

import os
import sys
import re
import time
import subprocess
from contextlib import contextmanager

# Cross-process file locking. fcntl is POSIX-only; msvcrt is Windows-only.
try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows
    _fcntl = None
try:
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - POSIX
    _msvcrt = None


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

HOT_BUCKET_VERBS = {"create", "triage", "start", "block", "defer", "review", "done"}

LEGACY_PRIORITY_TO_P = {"Critical": "P0", "High": "P1", "Medium": "P2", "Low": "P3"}

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
rvc context STORY-01        # target + linked refs + ranked related context
rvc issue STORY-01 done     # → done
```

Transitions are plain `git mv`, so every move is recoverable through git history.

## Protocol

Read `{VAULT}/{ROUTING}` first — it overrides the rest of this file.
"""

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
    if "{" in body and "}" in body:
        raise ValueError(f"README_TEMPLATE placeholder not replaced: {body[body.index('{'):body.index('}') + 1]}")
    with open(readme, "w") as f:
        f.write(body)
    print(f"[RVC] Wrote project README: {readme}")


VAULT_GITIGNORE_LINES = (
    ".rvc-create.lock",
    ".rvc-context-cache.json",
    ".rvc-context-cache.sqlite",
    ".rvc-context-cache.sqlite-wal",
    ".rvc-context-cache.sqlite-shm",
    "**/.obsidian/workspace.json",
    ".~lock.*#",
)


def _write_vault_gitignore(vault_dir):
    path = os.path.join(vault_dir, ".gitignore")
    existing = []
    if os.path.exists(path):
        with open(path, "r", errors="replace") as f:
            existing = [line.strip() for line in f]
    missing = [line for line in VAULT_GITIGNORE_LINES if line not in existing]
    if not missing:
        print(f"[RVC] Vault .gitignore already covers volatile files: {path}")
        return
    with open(path, "a") as f:
        if existing and existing[-1] != "":
            f.write("\n")
        f.write("# RVC + Obsidian volatile state\n")
        for line in missing:
            f.write(line + "\n")
    print(f"[RVC] Wrote vault .gitignore: {path}")


def cmd_init(target_path=".", tree="legacy"):
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

    _write_vault_gitignore(vault_dir)

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

    _write_vault_gitignore(vault_dir)

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


def build_vault_index(vault_path):
    vault_index = {}
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") or d == ".obsidian"]
        for file in files:
            base_name = file.rsplit('.md', 1)[0]
            if base_name not in vault_index:
                vault_index[base_name] = os.path.join(root, file)
    return vault_index


def _parse_id_alias(item_id):
    m = re.match(r"^([A-Za-z]+)-0*(\d+)(?:-.*)?$", (item_id or "").strip())
    if not m:
        return None
    return m.group(1).lower(), int(m.group(2))


def _find_in_index(vault_index, item_id):
    clean_id = item_id.split('#')[0].strip()
    if not clean_id:
        return None
    if clean_id in vault_index:
        return vault_index[clean_id]
    for filename in vault_index.keys():
        if filename.startswith(clean_id + "-"):
            return vault_index[filename]
    want = _parse_id_alias(clean_id)
    if want:
        for filename in vault_index.keys():
            if _parse_id_alias(filename) == want:
                return vault_index[filename]
    return None


def find_file_by_id(vault_path, item_id):
    return _find_in_index(build_vault_index(vault_path), item_id)


# ── ID Minting & Process Lock ───────────────────────────────────────────────
LOCK_FILE_NAME = ".rvc-create.lock"
LOCK_TIMEOUT = 30


def _lock_acquire(fd):
    if _fcntl is not None:
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            return True
        except OSError:
            return False
    if _msvcrt is not None:
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    return True


def _lock_release(fd):
    try:
        if _fcntl is not None:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        elif _msvcrt is not None:
            os.lseek(fd, 0, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


@contextmanager
def vault_create_lock(vault_path):
    lock_path = os.path.join(vault_path, LOCK_FILE_NAME)
    deadline = time.monotonic() + LOCK_TIMEOUT
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        while not _lock_acquire(fd):
            if time.monotonic() >= deadline:
                msg = (f"Lock {lock_path} held > {LOCK_TIMEOUT}s by another "
                       "process — aborting to avoid a duplicate-ID race.")
                raise TimeoutError(msg)
            time.sleep(0.05)
        try:
            os.truncate(fd, 0)
            os.write(fd, f"pid={os.getpid()}\n".encode())
        except OSError:
            pass
        yield
    finally:
        _lock_release(fd)
        os.close(fd)


def _next_id(vault_path, prefix="STORY"):
    max_num = 0
    width = 2
    tree = resolve_tree(vault_path)
    for d in tree_dirs(tree):
        root = os.path.join(vault_path, d)
        if not os.path.isdir(root):
            continue
        for _, _, files in os.walk(root):
            for f in files:
                m = re.match(rf'^{re.escape(prefix)}-(\d+)', f)
                if m:
                    digits = m.group(1)
                    num = int(digits)
                    if num > max_num:
                        max_num = num
                        width = len(digits)
                    elif num == max_num:
                        width = max(width, len(digits))
    return f"{prefix}-{str(max_num + 1).zfill(width)}"
