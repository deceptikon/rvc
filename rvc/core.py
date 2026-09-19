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
    1. A .rvc-root marker file (allows any directory name) — a project-root
       marker with `vault=<name>` descends into that subdirectory (STORY-037)
    2. A directory with RVC structure (10_Issues/ + .obsidian/)
    3. A directory literally named 'vault' (backward compat)
    """
    curr = os.path.abspath(start_path)
    if not os.path.isdir(curr):
        # callers may hand over a file (e.g. a feedback letter); climb to its dir
        curr = os.path.dirname(curr)
    max_depth = 8
    depth = 0
    while curr != os.path.dirname(curr) and depth < max_depth:
        depth += 1
        # 1. Check for .rvc-root marker in current directory
        if os.path.exists(os.path.join(curr, ".rvc-root")):
            return _ref_vault_dir(curr)
        # 2. Check children for .rvc-root marker or RVC structure
        try:
            for entry in os.listdir(curr):
                child = os.path.join(curr, entry)
                if not os.path.isdir(child):
                    continue
                if os.path.isfile(os.path.join(child, ".rvc-root")):
                    return _ref_vault_dir(child)
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


def _ref_vault_dir(marker_dir):
    """The vault a `.rvc-root` marker points at.

    A project-root marker carries `vault=<rel>` naming its vault subdirectory
    (STORY-037 layout). Descend into it only when the child exists AND has no
    marker of its own: self-referential inner markers (`vault=rvc-vault` inside
    `rvc-vault/`) and old flat markers (no `vault=` line) must stay put — no
    recursion, no mis-descent.
    """
    root_file = os.path.join(marker_dir, ".rvc-root")
    if os.path.isfile(root_file):
        try:
            with open(root_file, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("vault="):
                        ref = line[len("vault="):].strip()
                        if ref and "/" not in ref and "\\" not in ref and ref != ".":
                            child = os.path.join(marker_dir, ref)
                            if (os.path.isdir(child)
                                    and not os.path.isfile(os.path.join(child, ".rvc-root"))):
                                return child
                        break
        except OSError:
            pass
    return marker_dir


def find_marker_dir(vault_path):
    """Nearest directory holding `.rvc-root`: the vault itself first, then ancestors.

    New-layout vaults have no marker inside — its project root does. Every reader
    and writer of `.rvc-root` (tree config, plate lanes, `push=`, the automatic
    feedback config) resolves through here so a single marker stays authoritative.
    """
    curr = os.path.abspath(vault_path)
    while curr != os.path.dirname(curr):
        if os.path.isfile(os.path.join(curr, ".rvc-root")):
            return curr
        curr = os.path.dirname(curr)
    return None


def marker_file(vault_path):
    """Path of the effective `.rvc-root` for a vault (its own, else an ancestor's)."""
    root_dir = find_marker_dir(vault_path)
    return os.path.join(root_dir, ".rvc-root") if root_dir else None


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
    """Read `tree.<verb>=<dir>` lines from the effective .rvc-root. {} if none (→ legacy)."""
    root_file = marker_file(vault_path) or os.path.join(vault_path, ".rvc-root")
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
    """(Re)write the effective .rvc-root with a tree.* block, preserving a leading vault= line."""
    root_file = marker_file(vault_path) or os.path.join(vault_path, ".rvc-root")
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
| `.rvc-root` | Project-root marker: `vault=<name>` + `tree.<verb>=<dir>` map |
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


DEFAULT_VAULT_NAME = "0-vault"


def _existing_vault_name(root):
    """The `vault=<name>` value in <root>/.rvc-root, or None if absent."""
    root_file = os.path.join(root, ".rvc-root")
    if not os.path.isfile(root_file):
        return None
    with open(root_file, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("vault="):
                value = line[len("vault="):].strip()
                return value or None
    return None


def _prompt_vault_name(default):
    """Ask for the vault directory name; silent default when not a tty."""
    if not sys.stdin.isatty():
        return default
    try:
        answer = input(f"Vault directory name [{default}]: ").strip()
    except (EOFError, OSError):
        return default
    if answer and (answer in (".", "..") or "/" in answer or "\\" in answer
                   or answer.startswith(".")):
        print(f"[RVC] Invalid vault name {answer!r} — using {default!r}")
        return default
    return answer or default


def _ensure_rvc_root(root, vault_name, tree):
    """Write or extend the project-root marker: `vault=<name>` + missing tree.* lines.

    Additive only — existing lines (including user config such as `feedback.to=`
    or `push=true`) are preserved verbatim and never overwritten.
    """
    root_file = os.path.join(root, ".rvc-root")
    existing_lines = []
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            existing_lines = f.readlines()
    if not existing_lines:
        with open(root_file, "w") as f:
            f.write("# RVC vault root\n")
            f.write(f"vault={vault_name}\n")
            for verb, d in sorted(tree.items()):
                f.write(f"tree.{verb}={d}\n")
        print(f"[RVC] Wrote project .rvc-root: {root_file}")
        return
    has_vault = any(l.strip().startswith("vault=") for l in existing_lines)
    present = {l.strip().split("=", 1)[0][len("tree."):] for l in existing_lines
               if l.strip().startswith("tree.")}
    missing = [f"tree.{verb}={d}\n" for verb, d in sorted(tree.items()) if verb not in present]
    if has_vault and not missing:
        print(f"[RVC] .rvc-root already complete: {root_file}")
        return
    with open(root_file, "w") as f:
        for line in existing_lines:
            f.write(line if line.endswith("\n") else line + "\n")
        if not has_vault:
            f.write(f"vault={vault_name}\n")
        for text in missing:
            f.write(text)
    print(f"[RVC] Extended project .rvc-root: {root_file}")


def cmd_init(target_path=".", vault_name=None):
    """Initialize a project: vault subdirectory (default `0-vault`, prompted) plus
    `.rvc-root` and `.gitignore` at the project root.

    Always the same new structure (STORY-037 — the legacy/newvault dualism is
    gone). Re-runs never overwrite: they append missing files and marker/
    gitignore lines and reuse the existing vault name (no re-prompt).
    """
    root = os.path.abspath(target_path)
    os.makedirs(root, exist_ok=True)

    existing_name = _existing_vault_name(root)
    root_file = os.path.join(root, ".rvc-root")
    if os.path.isfile(root_file) and not existing_name:
        with open(root_file, "r", errors="replace") as f:
            looks_like_vault = any(l.strip().startswith("tree.") for l in f)
        if looks_like_vault:
            print(f"[RVC] {root} is already an RVC vault (flat marker, no vault name). Nothing to do.")
            return root
    if not os.path.isfile(root_file):
        # Legacy dogfooding repos own their vault as an inner dir with its own
        # self-referential marker (e.g. `rvc-vault/.rvc-root` → `vault=rvc-vault`).
        # Such a project already has a vault — never scaffold a second one beside it.
        try:
            for entry in sorted(os.listdir(root)):
                child = os.path.join(root, entry)
                if os.path.isdir(child) and os.path.isfile(os.path.join(child, ".rvc-root")):
                    print(f"[RVC] {root} already owns a vault at {child} (inner .rvc-root). Nothing to do.")
                    return root
        except OSError:
            pass
    if vault_name is None:
        vault_name = existing_name or _prompt_vault_name(DEFAULT_VAULT_NAME)
    if existing_name and vault_name != existing_name:
        print(f"[RVC] Keeping existing vault name '{existing_name}' (never overwrites)")
        vault_name = existing_name

    vault = os.path.join(root, vault_name)
    t = dict(NEWVAULT_TREE)
    for d in tree_dirs(t) + [".obsidian"]:
        os.makedirs(os.path.join(vault, d), exist_ok=True)

    _ensure_rvc_root(root, vault_name, t)
    _write_vault_gitignore(root)

    reglament = "10_CONTEXT/ROUTING.md"
    routing_path = os.path.join(vault, reglament)
    if os.path.exists(routing_path):
        print(f"[RVC] Keeping existing {reglament} (re-run is non-destructive)")
    else:
        with open(routing_path, "w") as f:
            f.write("# Vault Routing\n")
    _link_context_roots(root, vault_name, reglament)
    _write_project_readme(root, os.path.basename(root), vault_name, "newvault")
    print(f"[RVC] Initialized RVC vault '{vault_name}' at {vault}")
    print(f"[RVC] Marker + gitignore at project root: {root}/.rvc-root, {root}/.gitignore")
    print(f"[RVC] Tip: open {vault} in Obsidian")
    return vault


def cmd_project_init(target_path=".", vault_name=None, tree="legacy"):
    """Compatibility alias for cmd_init: vault in a named subdirectory.

    `tree` is accepted for old callers but ignored — init always produces the
    new structure (STORY-037: no legacy/newvault dualism).
    """
    return cmd_init(target_path, vault_name)


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


def _pid_alive(pid):
    """Cheap liveness probe: does a process with this pid exist right now?"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    return True


def _lock_record(fd):
    """Read the `pid=<n>` diagnostic record currently in the lock file."""
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        return os.read(fd, 64).decode(errors="replace").strip()
    except OSError:
        return ""


@contextmanager
def vault_create_lock(vault_path):
    lock_path = os.path.join(vault_path, LOCK_FILE_NAME)
    deadline = time.monotonic() + LOCK_TIMEOUT
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        while not _lock_acquire(fd):
            if time.monotonic() >= deadline:
                holder = _lock_record(fd)
                msg = (f"Lock {lock_path} held > {LOCK_TIMEOUT}s by another "
                       "process — aborting to avoid a duplicate-ID race.")
                if holder:
                    msg = msg.replace("by another process", f"by {holder}")
                raise TimeoutError(msg)
            time.sleep(0.05)

        # The flock is the authoritative lock; the pid record is diagnostic. If
        # it names a dead process, the marker is a leftover from an interrupted
        # create — a crashed holder's flock was released by the kernel, so this
        # marker was never going to block us; say so instead of letting a stale
        # `pid=` file read as an active lock (STORY-130).
        written = _lock_record(fd)
        m = re.match(r"^pid=(\d+)$", written)
        if m and not _pid_alive(m.group(1)):
            print(f"[RVC] Reclaiming stale create-lock "
                  f"({LOCK_FILE_NAME}: pid={m.group(1)} is gone).")
        try:
            os.truncate(fd, 0)
            os.write(fd, f"pid={os.getpid()}\n".encode())
        except OSError:
            pass
        yield
    finally:
        # Clean up so a successful create leaves no residue (STORY-130: the file
        # used to accumulate untracked at the vault root). Unlink only while the
        # path still names the inode we locked, and only while we still hold the
        # flock: waiters that already opened this inode keep serializing among
        # themselves, and a brand-new opener after the unlink starts fresh. The
        # inode check guarantees we never delete a replacement file.
        try:
            st_path = os.stat(lock_path)
            st_fd = os.fstat(fd)
            if st_path.st_dev == st_fd.st_dev and st_path.st_ino == st_fd.st_ino:
                os.remove(lock_path)
        except OSError:
            pass
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
