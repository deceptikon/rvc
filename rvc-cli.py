#!/usr/bin/env python3
import os
import sys
import re
import json
import time
import math
import hashlib
import argparse
import datetime as dt
import subprocess
from contextlib import contextmanager

# Cross-process file locking. fcntl is POSIX-only; msvcrt is Windows-only.
# Imported defensively so the CLI loads on both platforms instead of dying at
# import time on the missing module (STORY-013 AC4: "fcntl on Linux, msvcrt on
# Windows"). If neither exists, vault_create_lock degrades to a no-op.
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

# Legacy priority words → the P0-P3 vocabulary that newvault trees sort by. Used only when the
# vault's own tree declares a `block` bucket (i.e. it is newvault-shaped); legacy vaults keep
# Low/Medium/High/Critical untouched.
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
rvc context STORY-01        # target + linked refs + ranked related context
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


# Files every RVC/Obsidian vault should keep out of git. The lock file must be
# ignored in EVERY vault, not just this repo's root — a stray untracked
# `.rvc-create.lock` is noise in any host project. `rvc init` / `rvc project init`
# append these to the vault's own .gitignore (idempotent, non-clobbering).
VAULT_GITIGNORE_LINES = (
    ".rvc-create.lock",
    ".rvc-context-cache.json",
    "**/.obsidian/workspace.json",
    ".~lock.*#",
)


def _write_vault_gitignore(vault_dir):
    """Ensure <vault>/.gitignore covers RVC/Obsidian volatile files.

    Idempotent: appends only the lines not already present, preserves any
    existing content. Never fails the init if the file is unwritable.
    """
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

def sync_after(vault_path, file_paths, msg, skip_ci=True):
    git_root = find_git_root(vault_path)
    if git_root:
        print("[RVC] Committing state...")
        for fp in file_paths:
            run_cmd(f"git add '{fp}'", cwd=git_root)
        # Add [skip ci] tag by default for vault transitions, can be overridden
        if skip_ci:
            # If message already contains [skip ci], don't duplicate
            if "[skip ci]" not in msg:
                commit_msg = f"{msg} [skip ci]"
            else:
                commit_msg = msg
        else:
            commit_msg = msg
        run_cmd(f"git commit -m '{commit_msg}'", cwd=git_root)
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

def _parse_id_alias(item_id):
    """Parse `PREFIX-NN[-title]` into (lowercase prefix, int) for unpadded matching.

    `STORY-033`, `STORY-33`, `STORY-033-Some-Title` and `story-33` all parse to
    `("story", 33)`; `Q-STORY-106` and `ROUTING` return None (not an id shape).
    """
    m = re.match(r"^([A-Za-z]+)-0*(\d+)(?:-.*)?$", (item_id or "").strip())
    if not m:
        return None
    return m.group(1).lower(), int(m.group(2))


def _find_in_index(vault_index, item_id):
    """Resolve an id against a prebuilt index (exact, prefix, then alias match)."""
    clean_id = item_id.split('#')[0].strip()
    if not clean_id:
        return None

    # Exact match first
    if clean_id in vault_index:
        return vault_index[clean_id]

    # Prefix match (e.g., item_id="STORY-05" matches "STORY-05-some-title")
    for filename in vault_index.keys():
        if filename.startswith(clean_id + "-"):
            return vault_index[filename]

    # Unpadded numerals (STORY-33 == STORY-033 == story-33)
    want = _parse_id_alias(clean_id)
    if want:
        for filename in vault_index.keys():
            if _parse_id_alias(filename) == want:
                return vault_index[filename]
    return None


def find_file_by_id(vault_path, item_id):
    return _find_in_index(build_vault_index(vault_path), item_id)

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

# ── Semantic context retrieval: `rvc context` (STORY-033) ────────────────────
# Zero-dependency BM25 over the whole vault, stdlib only. Identity is the
# immutable Document ID (`STORY-033`, `ROUTING`, …); the cache keeps a path
# pointer beside the terms, so a folder transition (`git mv`) repaths with zero
# re-tokenization. A missing or corrupt cache cold-starts transparently.
#
# Ranking policy (rationale in DECISIONS.md, 2026-09-16):
# - Sections are scored independently; a document's score is its best section.
# - Archive buckets (tree.evict / tree.supersede) are indexed — a hard wikilink
#   may point at them — but are never offered as soft suggestions: evicted docs
#   are not live context.
# - Documents under the vault's roadmap/knowledge dir carry a prior (root x1.5,
#   nested x1.2): `rvc context` exists to surface the constitution, DECISIONS,
#   GOTCHAS and specs, not debate transcripts. Measured recall@5 on the
#   STORY-033 hand-labeled benchmark: 69% without the prior, 92% with it.
CONTEXT_CACHE_NAME = ".rvc-context-cache.json"
CONTEXT_CACHE_VERSION = 1
CONTEXT_DEFAULT_TOP_K = 3
CONTEXT_DEFAULT_BUDGET = 40000
CONTEXT_BM25_K1 = 1.5
# b=1.0 is full length normalization: a long debate transcript must not outrank
# a short reference by accumulating weak matches. Measured on the STORY-033
# benchmark: recall@5 77% at b=0.75 (okapi default) vs 92% at b=1.0.
CONTEXT_BM25_B = 1.0
CONTEXT_SUMMARY_CHARS = 500
CONTEXT_MATCH_LIMIT = 6
CONTEXT_KNOWLEDGE_ROOT_BOOST = 1.5
CONTEXT_KNOWLEDGE_SUBDIR_BOOST = 1.2

CONTEXT_TRUNCATED_FMT = "... [truncated {n} characters to satisfy budget] ..."
CONTEXT_OMITTED_FMT = "... [omitted {n} characters to satisfy budget] ..."

CONTEXT_STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have
he her his how i if in into is it its may might more most must no nor not of
on or our out over own said she should so some such than that the their them
then there these they this those to too under until up upon us use used using
was we were what when where which while who whom why will with would you your
""".split())

CONTEXT_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*")
CONTEXT_H1_RE = re.compile(r"^#\s+(.*)$")
CONTEXT_H2_RE = re.compile(r"^#{2,6}\s+(.*)$")
CONTEXT_FENCE_RE = re.compile(r"^\s*```")
CONTEXT_TITLE_KEYS = frozenset(("title", "id", "aliases"))
CONTEXT_TAG_KEYS = frozenset(("tags", "domain_tags", "keywords"))


def _context_canon(token):
    """Canonical token form: `STORY-013` and `STORY-13` become `story-13`."""
    parts = re.split(r"([-_.])", token)
    for i, part in enumerate(parts):
        if i % 2 == 0 and part.isdigit() and len(part) > 1:
            parts[i] = part.lstrip("0") or "0"
    return "".join(parts)


def _context_emit(weights, text, weight, surfaces=None):
    """Accumulate weighted terms from `text`; kebab ids also emit their parts."""
    for match in CONTEXT_TOKEN_RE.finditer(text):
        raw = match.group(0)
        token = _context_canon(raw.lower())
        if len(token) >= 2 and token not in CONTEXT_STOPWORDS:
            weights[token] = weights.get(token, 0.0) + weight
            if surfaces is not None and token not in surfaces:
                surfaces[token] = raw
        for part in re.split(r"[-_.]", raw):
            sub = _context_canon(part.lower())
            if sub == token or len(sub) < 2 or sub in CONTEXT_STOPWORDS:
                continue
            weights[sub] = weights.get(sub, 0.0) + weight * 0.5
            if surfaces is not None and sub not in surfaces:
                surfaces[sub] = part


def _context_chunk_terms(chunk, surfaces=None):
    """Weighted terms for one section: title/id 3x, tags 2.5x, headings 2x."""
    weights = {}
    lines = chunk.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", lines[i])
            if m:
                key = m.group(1).lower()
                if key in CONTEXT_TITLE_KEYS:
                    _context_emit(weights, m.group(2), 3.0, surfaces)
                elif key in CONTEXT_TAG_KEYS:
                    _context_emit(weights, m.group(2), 2.5, surfaces)
                else:
                    _context_emit(weights, m.group(2), 1.5, surfaces)
            i += 1
        i += 1
    in_fence = False
    for line in lines[i:]:
        if CONTEXT_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            _context_emit(weights, line, 1.0, surfaces)
            continue
        m1 = CONTEXT_H1_RE.match(line)
        if m1:
            _context_emit(weights, m1.group(1), 3.0, surfaces)
            continue
        m2 = CONTEXT_H2_RE.match(line)
        if m2:
            _context_emit(weights, m2.group(1), 2.0, surfaces)
            continue
        _context_emit(weights, line, 1.0, surfaces)
    return weights


def _context_chunks(text):
    """Split a doc into citable chunks: frontmatter, then one chunk per heading."""
    chunks, current, in_fence = [], [], False
    for line in text.splitlines():
        if CONTEXT_FENCE_RE.match(line):
            in_fence = not in_fence
        if not in_fence and (CONTEXT_H1_RE.match(line) or CONTEXT_H2_RE.match(line)) and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))
    return [c for c in chunks if c.strip()]


def _context_terms(text, surfaces=None):
    """Weighted term footprint of a document (merge of its chunks)."""
    merged = {}
    for chunk in _context_chunks(text):
        for token, weight in _context_chunk_terms(chunk, surfaces=surfaces).items():
            merged[token] = merged.get(token, 0.0) + weight
    return merged


def _context_split_frontmatter(text):
    """(raw frontmatter incl. fences, body) — (None, text) when absent."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    return text[:end + 4], text[end + 4:]


def _context_summary(text):
    """Frontmatter + title + heading outline + first 500 chars (AC4 trim form)."""
    raw, body = _context_split_frontmatter(text)
    headings = re.findall(r"(?m)^#{1,6}\s+.*$", body)
    stripped = re.sub(r"(?m)^#{1,6}\s+.*$", "", body).strip()
    parts = [raw] if raw else []
    parts.extend(headings)
    if stripped:
        parts.append(stripped[:CONTEXT_SUMMARY_CHARS])
    return "\n".join(parts)


def _context_goal_summary(text):
    """Frontmatter + goal/problem/acceptance sections (for --mode summary)."""
    raw, body = _context_split_frontmatter(text)
    sections = re.split(r"(?m)^(##\s+.*)$", body)
    kept = []
    for i in range(1, len(sections), 2):
        heading = sections[i]
        content = sections[i + 1] if i + 1 < len(sections) else ""
        if re.search(r"goal|acceptance|problem|context|summary|objective|why",
                     heading, re.I):
            kept.append((heading + content).strip())
    if not kept:
        return _context_summary(text)
    parts = [raw] if raw else []
    parts.append("\n\n".join(kept))
    return "\n".join(parts)


def _context_doc_id(rel_path, text):
    """Immutable Document ID: frontmatter `id:` else the filename's id shape."""
    fields = plate_frontmatter(text)
    doc_id = fields.get("id")
    if doc_id:
        return doc_id
    base = os.path.basename(rel_path)
    if base.endswith(".md"):
        base = base[:-3]
    m = re.match(r"^([A-Za-z]+-\d+)", base)
    return m.group(1) if m else base


def _context_doc_title(text, rel_path):
    """Human title: frontmatter `title:` else the first H1 else the filename."""
    fields = plate_frontmatter(text)
    if fields.get("title"):
        return fields["title"].strip().strip("\"'")
    m = re.search(r"(?m)^#\s+(.*)$", text)
    if m:
        return m.group(1).strip()
    return os.path.basename(rel_path)


def context_cache_path(vault_path):
    return os.path.join(vault_path, CONTEXT_CACHE_NAME)


def _context_hash(text):
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def _context_read(vault_path, rel_path):
    try:
        with open(os.path.join(vault_path, rel_path), "r",
                  encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _context_scan(vault_path):
    """{rel_path: (mtime, size)} for every .md file (hidden dirs skipped)."""
    found = {}
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            found[os.path.relpath(path, vault_path).replace(os.sep, "/")] = (
                st.st_mtime, st.st_size)
    return found


def _context_empty_cache():
    return {"version": CONTEXT_CACHE_VERSION, "docs": {}, "postings": {},
            "chunk_count": 0, "chunk_total_len": 0.0}


def _context_load_cache(vault_path):
    """Load the cache; None when missing, unreadable, or structurally invalid."""
    try:
        with open(context_cache_path(vault_path), "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(cache, dict) or cache.get("version") != CONTEXT_CACHE_VERSION:
        return None
    if not isinstance(cache.get("docs"), dict) or not isinstance(cache.get("postings"), dict):
        return None
    if not isinstance(cache.get("chunk_count"), int):
        return None
    if not isinstance(cache.get("chunk_total_len"), (int, float)):
        return None
    for meta in cache["docs"].values():
        if not isinstance(meta, dict) or "path" not in meta or "chunk_lens" not in meta:
            return None
    return cache


def _context_save_cache(vault_path, cache):
    """Atomic best-effort write — a torn cache never replaces a good one."""
    path = context_cache_path(vault_path)
    tmp = f"{path}.tmp{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, separators=(",", ":"), ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _context_index_doc(cache, vault_path, rel_path, text, mtime, size):
    """(Re)tokenize one document into the cache; returns its Document ID."""
    doc_id = _context_doc_id(rel_path, text)
    if doc_id in cache["docs"]:
        _context_remove_doc(cache, doc_id)
    chunks = _context_chunks(text)
    chunk_lens = []
    for ci, chunk in enumerate(chunks):
        terms = _context_chunk_terms(chunk)
        chunk_lens.append(sum(terms.values()))
        for token, weight in terms.items():
            cache["postings"].setdefault(token, {}).setdefault(doc_id, []).append(
                [ci, round(weight, 4)])
    cache["docs"][doc_id] = {
        "path": rel_path,
        "mtime": mtime,
        "size": size,
        "hash": _context_hash(text),
        "chunks": len(chunks),
        "chunk_lens": chunk_lens,
    }
    cache["chunk_count"] += len(chunks)
    cache["chunk_total_len"] += sum(chunk_lens)
    return doc_id


def _context_remove_doc(cache, doc_id):
    meta = cache["docs"].pop(doc_id, None)
    if meta is None:
        return
    cache["chunk_count"] = max(0, cache["chunk_count"] - meta.get("chunks", 0))
    cache["chunk_total_len"] = max(
        0.0, cache["chunk_total_len"] - sum(meta.get("chunk_lens", [])))
    for token in list(cache["postings"].keys()):
        postings = cache["postings"][token]
        if doc_id in postings:
            del postings[doc_id]
            if not postings:
                del cache["postings"][token]


def context_cache_update(vault_path, force=False):
    """Bring `.rvc-context-cache.json` up to date; returns the cache dict.

    Incremental by design: only added/altered/deleted files are touched. A file
    whose stat matches a vanished path is the same document moved — it repaths
    with zero re-tokenization. A corrupt cache cold-starts transparently.
    """
    cache = None if force else _context_load_cache(vault_path)
    scanned = _context_scan(vault_path)
    if cache is None:
        cache = _context_empty_cache()
        by_path = {}
        dirty = True
    else:
        by_path = {meta["path"]: doc_id for doc_id, meta in cache["docs"].items()}
        dirty = False

    # 1. Repath first: an added path whose stat matches a vanished doc is a move.
    vanished = [doc_id for doc_id, meta in cache["docs"].items()
                if meta["path"] not in scanned]
    added = [path for path in scanned if path not in by_path]
    for path in list(added):
        mtime, size = scanned[path]
        for doc_id in list(vanished):
            meta = cache["docs"][doc_id]
            if meta["size"] == size and abs(meta["mtime"] - mtime) < 1e-4:
                meta["path"] = path
                meta["mtime"], meta["size"] = mtime, size
                by_path[path] = doc_id
                added.remove(path)
                vanished.remove(doc_id)
                dirty = True
                break

    # 2. Deletions.
    for doc_id in vanished:
        _context_remove_doc(cache, doc_id)
        dirty = True

    # 3. Additions and modifications.
    for rel_path, (mtime, size) in scanned.items():
        if rel_path in added:
            text = _context_read(vault_path, rel_path)
            if text is None:
                continue
            _context_index_doc(cache, vault_path, rel_path, text, mtime, size)
            dirty = True
            continue
        doc_id = by_path.get(rel_path)
        if doc_id is None or doc_id not in cache["docs"]:
            continue
        meta = cache["docs"][doc_id]
        if meta["mtime"] == mtime and meta["size"] == size:
            continue
        text = _context_read(vault_path, rel_path)
        if text is None:
            continue
        if _context_hash(text) == meta["hash"]:
            meta["mtime"], meta["size"] = mtime, size
            dirty = True
            continue
        old_id = doc_id
        new_id = _context_index_doc(cache, vault_path, rel_path, text, mtime, size)
        if new_id != old_id and old_id in cache["docs"]:
            _context_remove_doc(cache, old_id)
        dirty = True

    if dirty:
        _context_save_cache(vault_path, cache)
    return cache


def context_cache_repath(vault_path, old_path, new_path):
    """Update a document's path pointer after a move — no re-tokenization."""
    cache = _context_load_cache(vault_path)
    if cache is None:
        return
    old_rel = os.path.relpath(old_path, vault_path).replace(os.sep, "/")
    new_rel = os.path.relpath(new_path, vault_path).replace(os.sep, "/")
    for meta in cache["docs"].values():
        if meta.get("path") == old_rel:
            meta["path"] = new_rel
            try:
                st = os.stat(new_path)
                meta["mtime"], meta["size"] = st.st_mtime, st.st_size
            except OSError:
                pass
            _context_save_cache(vault_path, cache)
            return


def _context_archive_dirs(tree):
    """Buckets whose docs are never soft suggestions (indexed, not offered)."""
    dirs = [tree[v].rstrip("/") for v in ("evict", "supersede")
            if tree and tree.get(v)]
    return tuple(dirs) if dirs else ("90_ARCHIVE",)


def _context_is_archived(rel_path, archive_dirs):
    return any(rel_path == d or rel_path.startswith(d + "/") for d in archive_dirs)


def _context_knowledge_prior(rel_path, tree):
    """Prior for docs under the vault's knowledge root (root > nested)."""
    root = (tree or {}).get("roadmap")
    if not root:
        return 1.0
    root = root.rstrip("/")
    if rel_path == root or rel_path.startswith(root + "/"):
        rest = rel_path[len(root):].lstrip("/")
        return CONTEXT_KNOWLEDGE_SUBDIR_BOOST if "/" in rest else CONTEXT_KNOWLEDGE_ROOT_BOOST
    return 1.0


def context_rank(cache, term_weights, surfaces=None, top_k=CONTEXT_DEFAULT_TOP_K,
                 exclude_ids=(), exclude_paths=(), tree=None):
    """Rank docs against a weighted term footprint; returns top scoring entries.

    Each entry is `(doc_id, score, matched_surfaces, rel_path)`, best first.
    A document's score is its best matching section (chunk-level BM25).
    """
    docs = cache.get("docs") or {}
    postings = cache.get("postings") or {}
    n_docs = len(docs)
    if not n_docs or not term_weights:
        return []
    exclude_ids = set(exclude_ids)
    exclude_paths = set(exclude_paths)
    archive_dirs = _context_archive_dirs(tree)
    chunk_total = cache.get("chunk_total_len", 0.0)
    chunk_count = cache.get("chunk_count", 0)
    chunk_avg = (chunk_total / chunk_count) if chunk_count else 1.0
    if chunk_avg <= 0:
        chunk_avg = 1.0

    chunk_scores = {}
    for token, qw in term_weights.items():
        postings_for_term = postings.get(token)
        if not postings_for_term:
            continue
        df = len(postings_for_term)
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        for doc_id, entries in postings_for_term.items():
            if doc_id in exclude_ids:
                continue
            meta = docs.get(doc_id)
            if meta is None:
                continue
            scores = chunk_scores.setdefault(doc_id, {})
            chunk_lens = meta.get("chunk_lens", [])
            for ci, weight in entries:
                clen = chunk_lens[ci] if ci < len(chunk_lens) else 1.0
                denom = weight + CONTEXT_BM25_K1 * (
                    1 - CONTEXT_BM25_B + CONTEXT_BM25_B * (clen / chunk_avg))
                scores[ci] = scores.get(ci, 0.0) + (
                    qw * idf * weight * (CONTEXT_BM25_K1 + 1) / denom)

    ranked = []
    for doc_id, scores in chunk_scores.items():
        meta = docs[doc_id]
        rel_path = meta["path"]
        if rel_path in exclude_paths or _context_is_archived(rel_path, archive_dirs):
            continue
        best_ci = max(scores, key=lambda ci: (scores[ci], -ci))
        score = scores[best_ci] * _context_knowledge_prior(rel_path, tree)
        ranked.append((score, doc_id, best_ci, rel_path))
    ranked.sort(key=lambda row: (-row[0], row[3]))

    results = []
    for score, doc_id, best_ci, rel_path in ranked[:top_k]:
        contributions = []
        for token, qw in term_weights.items():
            entries = postings.get(token, {}).get(doc_id)
            if not entries:
                continue
            for ci, weight in entries:
                if ci == best_ci:
                    contributions.append((qw * weight, token))
                    break
        contributions.sort(key=lambda row: (-row[0], row[1]))
        matched = [((surfaces or {}).get(token, token))
                   for _, token in contributions[:CONTEXT_MATCH_LIMIT]]
        results.append((doc_id, score, matched, rel_path))
    return results


def _context_block_body(block):
    form = block["form"]
    if form == "gone":
        return ""
    if form == "stub":
        return block.get("stub", "")
    if form == "full":
        return block["text"]
    if form == "summary":
        return block["summary"]
    if form == "trunc":
        limit = max(0, block.get("limit", 0))
        removed = max(0, len(block["text"]) - limit)
        return block["text"][:limit] + "\n" + CONTEXT_TRUNCATED_FMT.format(n=removed)
    return CONTEXT_OMITTED_FMT.format(n=len(block["text"]))


def _context_block_text(block):
    if block["form"] == "gone":
        return ""
    if block["form"] == "stub":
        return block.get("stub", "")
    parts = [block["header"]]
    parts.extend(block.get("meta", ()))
    body = _context_block_body(block)
    if body:
        parts.append(body)
    if block.get("footer"):
        parts.append(block["footer"])
    return "\n".join(parts)


def _context_assemble(target_id, target_title, target, hard_blocks, missing,
                      soft_blocks, budget, mode):
    """Render the context payload, degrading lowest-priority blocks first.

    Priority is target > hard refs > soft refs; within a tier the last item
    degrades first. Forms: full -> summary -> truncated -> omitted -> stub
    (one-line notice) -> gone.
    """
    if mode == "summary":
        for block in [target] + hard_blocks:
            block["form"] = "summary"
    order = list(reversed(soft_blocks)) + list(reversed(hard_blocks)) + [target]

    def render():
        header = f"# RVC Context Assembler: {target_id}"
        if target_title:
            header += f" ({target_title})"
        parts = [header, "", "## 1. Target Issue", _context_block_body(target)]
        visible_hard = [b for b in hard_blocks if b["form"] != "gone"]
        gone_hard = [b for b in hard_blocks if b["form"] == "gone"]
        if visible_hard or gone_hard or missing:
            parts.append("")
            parts.append("## 2. Explicit References (Hard Signals)")
            for block in visible_hard:
                parts.append(_context_block_text(block))
            for block in gone_hard:
                parts.append(block.get("stub", CONTEXT_OMITTED_FMT.format(n=len(block["text"]))))
            for link in missing:
                parts.append(f"--- REFERENCE [[{link}]] NOT FOUND IN VAULT ---")
        visible_soft = [b for b in soft_blocks if b["form"] != "gone"]
        gone_soft = [b for b in soft_blocks if b["form"] == "gone"]
        if visible_soft or gone_soft:
            parts.append("")
            parts.append("## 3. Discovered Related Context (Soft Signals — Top-K Semantic/BM25)")
            for block in visible_soft:
                parts.append(_context_block_text(block))
            if gone_soft:
                omitted = sum(len(b["text"]) for b in gone_soft)
                parts.append(
                    f"... [omitted {omitted} characters to satisfy budget across "
                    f"{len(gone_soft)} related item(s)] ...")
        return "\n".join(parts)

    text = render()
    guard = 0
    while len(text) > budget and guard < 500:
        guard += 1
        block = next((b for b in order if b["form"] != "gone"), None)
        if block is None:
            text = text[:max(0, budget)]
            break
        form = block["form"]
        if form == "full":
            block["form"] = "summary"
        elif form == "summary":
            excess = len(text) - budget
            notice = CONTEXT_TRUNCATED_FMT.format(n=len(block["text"]))
            block["form"] = "trunc"
            block["limit"] = max(0, len(block["summary"]) - excess - len(notice))
        elif form == "trunc":
            excess = len(text) - budget
            block["limit"] = max(0, block.get("limit", 0) - excess)
            if block["limit"] == 0:
                block["form"] = "omit"
        elif form == "omit":
            # Hard/soft refs leave a one-line stub so nothing is dropped
            # silently; the target only vanishes as the very last resort.
            block["form"] = "stub" if block.get("stub") else "gone"
        else:  # stub -> gone
            block["form"] = "gone"
        text = render()
    return text


def cmd_context(vault_path, item_id, top_k=CONTEXT_DEFAULT_TOP_K,
                budget=CONTEXT_DEFAULT_BUDGET, mode="full",
                no_semantic=False, reindex=False):
    """Assemble target + explicit wikilinks + Top-K BM25 matches (STORY-033)."""
    file_path = find_file_by_id(vault_path, item_id)
    if not file_path:
        print(f"Error: Item {item_id} not found.")
        sys.exit(1)

    rel_path = os.path.relpath(file_path, vault_path).replace(os.sep, "/")
    content = _context_read(vault_path, rel_path)
    if content is None:
        print(f"Error: could not read {file_path}")
        sys.exit(1)
    target_id = _context_doc_id(rel_path, content)
    target_title = _context_doc_title(content, rel_path)

    # Hard signals: deduplicated wikilinks, resolved against one index build.
    vault_index = build_vault_index(vault_path)
    links, seen = [], set()
    for raw_link in re.findall(r"\[\[(.*?)\]\]", content):
        name = raw_link.split("|")[0].split("#")[0].strip()
        if name and name not in seen:
            seen.add(name)
            links.append(raw_link)

    hard_blocks, missing = [], []
    hard_ids, hard_paths = set(), set()
    for link in links:
        name = link.split("|")[0].split("#")[0].strip()
        spec_path = _find_in_index(vault_index, name)
        if not spec_path:
            missing.append(link)
            continue
        spec_rel = os.path.relpath(spec_path, vault_path).replace(os.sep, "/")
        spec_text = _context_read(vault_path, spec_rel)
        if spec_text is None:
            missing.append(link)
            continue
        hard_ids.add(_context_doc_id(spec_rel, spec_text))
        hard_paths.add(spec_rel)
        hard_blocks.append({
            "kind": "hard",
            "header": f"--- REFERENCE: [[{link}]] ---\nFile: {spec_rel}",
            "footer": "--- END OF REFERENCE ---",
            "meta": (),
            "text": spec_text,
            "summary": _context_goal_summary(spec_text),
            "stub": f"--- REFERENCE: [[{link}]] {CONTEXT_OMITTED_FMT.format(n=len(spec_text))} ---",
            "form": "full",
        })

    soft_blocks = []
    if not no_semantic:
        cache = context_cache_update(vault_path, force=reindex)
        surfaces = {}
        terms = _context_terms(content, surfaces=surfaces)
        tree = resolve_tree(vault_path)
        ranked = context_rank(
            cache, terms, surfaces=surfaces, top_k=top_k,
            exclude_ids=hard_ids | {target_id},
            exclude_paths=hard_paths | {rel_path}, tree=tree)
        best_score = ranked[0][1] if ranked else 0.0
        for doc_id, score, matched, path in ranked:
            doc_text = _context_read(vault_path, path)
            if doc_text is None:
                continue
            display = (score / best_score) if best_score else 0.0
            soft_blocks.append({
                "kind": "soft",
                "header": f"--- RELATED: [[{path}]] (Relevance Score: {display:.2f}) ---",
                "footer": "--- END OF RELATED ---",
                "meta": ((f"Matched terms: {', '.join(matched)}",) if matched else ()),
                "text": doc_text,
                "summary": _context_summary(doc_text),
                "stub": f"--- RELATED: [[{path}]] {CONTEXT_OMITTED_FMT.format(n=len(doc_text))} ---",
                "form": "full",
            })

    target_block = {
        "kind": "target",
        "header": "",
        "footer": "",
        "meta": (),
        "text": content,
        "summary": _context_goal_summary(content),
        "form": "full",
    }
    print(_context_assemble(target_id, target_title, target_block, hard_blocks,
                            missing, soft_blocks, budget, mode))


def cmd_issue_action(vault_path, issue_id, action, skip_ci=True):
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

    # Eager index hook (STORY-033 constraint 5): move the path pointer without
    # re-tokenizing — identity (Document ID + content hash) is unchanged.
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


LOCK_FILE_NAME = ".rvc-create.lock"
LOCK_TIMEOUT = 30  # seconds; refuse to wedge a create behind a dead peer


def _lock_acquire(fd):
    """Non-blocking exclusive lock on an open fd. True if acquired.

    POSIX -> fcntl.flock; Windows -> msvcrt.locking (1 byte at offset 0).
    With neither primitive available, returns True so `create` still works
    (degraded: no cross-process protection, but never a hard failure).
    """
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
    """Release the lock taken by _lock_acquire (best-effort; never raises)."""
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
    """Cross-process advisory lock serializing ID minting + file creation.

    Held via fcntl.flock on POSIX (msvcrt on Windows), released automatically
    when the fd closes, so a crashed process cannot wedge the vault — no
    stale-lock cleanup needed. The lock file itself is never deleted; it lives
    beside .rvc-root and is git-ignored in every vault (`rvc init` writes the
    rule; see VAULT_GITIGNORE_LINES).

    With a timeout: if another create holds the lock longer than LOCK_TIMEOUT
    seconds, we assume it was interrupted or hung and fail loudly rather than
    block forever — surfacing the contention instead of wedging the CLI.
    """
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
        # Best-effort pid stamp for debugging; never let it break the lock.
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
    """Find the next sequential ID for a given prefix (e.g., STORY-30).

    Padding is derived from the width of the vault's existing high-water mark,
    so a 3-digit vault (STORY-010) keeps minting 3-digit ids (STORY-011) and a
    fresh vault starts at STORY-01. Mixed-width vaults keep the widest form.
    """
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


def cmd_create_issue(vault_path, title, prefix="STORY", issue_type="story",
                     priority="Medium", body="", directory=None,
                     epic="", extra_frontmatter=None, skip_ci=True):
    """Create a new issue file with proper frontmatter."""
    tree = resolve_tree(vault_path)
    # newvault trees sort a P0-P3 vocabulary (ADLAI ROUTING §5.3); the legacy words mint strays
    # there. A tree that declares a `block` bucket is newvault-shaped, so translate rather than
    # refuse — the caller's intent survives, the queue stays sortable.
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

    # Critical section: ID mint + file creation must be atomic across processes.
    # Two concurrent creates scanning for the max ID would otherwise both mint
    # STORY-XXX+1 and one silently overwrites the other's file.
    try:
        with vault_create_lock(vault_path):
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
                f"id: {issue_id}",
                f"title: {title}",
                f"type: {issue_type}",
                f"priority: {priority}",
            ]
            if epic:
                lines.append(f"epic: [[{epic}]]")
            lines.append(f"started: {today}")
            if extra_frontmatter:
                # Mint-time guard (STORY-029): on a block-bucket tree a `status:` field
                # is a constitutional violation — folder owns state. Refuse to mint it.
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
    except TimeoutError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Eager index hook (STORY-033 constraint 5): if a context cache already
    # exists, fold the new issue in so the next `rvc context` is warm.
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
    
    # Automatically commit the new issue file with [skip ci]
    sync_after(vault_path, [filepath], f"rvc: Created issue {issue_id}: {title}", skip_ci=skip_ci)
    
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


# ── Plate rendering: `rvc plate` ─────────────────────────────────────────────
# The ordered state of a vault, computed from the tree. The lane *rules* belong to the
# governing vault's constitution (ADLAI `ROUTING.md` §5.3); this renderer stays generic —
# verbs resolve through the vault's own tree, so a legacy vault without a `block` bucket
# yields empty decide lanes instead of crashing. Team-specific facts (who is who, who
# decides) are read from `.rvc-root`, never hardcoded here:
#
#   alias.Q=q,Qwen,qwen,qwen-code        canonical first, then every handle that means it
#   plate.owner=@deceptikon              the deciding seat on a `tables/` surface
#
# Identity is caller-supplied: without `--as` the CLI renders the tree lanes and says so,
# keeping `rvc` identity-free by default (the STORY-106-selftest-loop verdict). Passing
# `--as` does not make the CLI *know* anyone — it is a filter argument, and resolving
# "$AGENT / STATE.json" stays where the verdict put it: in the ritual driver.

PLATE_ASK_LINE_RE = re.compile(r"^\s*-\s*\[ \]\s*(.*)$")
PLATE_HANDLE_RE = re.compile(r"@([\w.+-]+)")
PLATE_SEP_RE = re.compile(r"\s+[-—:]\s+")
PLATE_HEADER_RE = re.compile(r"^##\s+([^@\n]+?)\s*@\s*(\d{4}-\d{2}-\d{2})", re.M)
PLATE_DATE_RE = re.compile(r"^\s*(?:updated|date|created)\s*:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
PLATE_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
PLATE_ISSUE_TYPES = ("story", "epic", "bug", "task")


def read_plate_config(vault_path):
    """Return ({lowercase handle → canonical}, owner_canonical) from `.rvc-root`."""
    aliases, owner = {}, None
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
                elif line.startswith("plate.owner"):
                    owner = line.partition("=")[2].strip() or None
    return aliases, owner


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


def cmd_plate(vault_path, as_alias=None, fmt="text", stale_days=7, today=None):
    """Render the plate: seven lanes computed from folders, priorities and open ask boxes."""
    tree = resolve_tree(vault_path)
    aliases, owner = read_plate_config(vault_path)
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

    if fmt == "json":
        payload = {
            "vault": vault_path,
            "as": me,
            "owner": owner,
            "today": today.isoformat(),
            "identity_lanes": bool(me),
            "lanes": {
                key: [
                    {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in row.items() if k != "asks"}
                    for row in rows
                ]
                for key, rows in lanes.items()
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
    print(f"PLATE — {os.path.basename(vault_path)} — {today.isoformat()} — derived from the tree")
    for key, rows in lanes.items():
        print(f"\n{titles[key]}  [{len(rows)}]")
        if not rows:
            print("  —")
            continue
        for row in rows:
            if key in ("owes_turn", "owner"):
                ask = f" — {row['ask']}" if row.get("ask") else ""
                print(f"  {row['path']}{ask}")
            elif key == "active":
                print(f"  {row['name']}  open={row['open_boxes']} done={row['done_boxes']}")
            elif key == "next":
                print(f"  {row['priority'] or '—':>3}  {row['name']}")
            elif key == "overdue":
                print(f"  {row['age_days']:>3}d  {row['path']}  (last: {row['last_speaker']})")
            elif key == "inbox":
                print(f"  {row['name']}  type={row['type'] or '—'}")
            else:
                print(f"  {row['name']}  pri={row['priority'] or '—'}")


# ── Constitution audit: `rvc doctor` (STORY-029) ─────────────────────────────
# Folder = state. On a tree that declares a `block` bucket (newvault-shaped), a
# `status:` frontmatter field is a refusal-grade violation and any `priority:`
# outside the P0-P3 vocabulary is drift. Legacy trees (no block bucket) keep
# their old filing conventions — this guard exists only where the law says the
# folder owns state.

P_VOCABULARY = ("P0", "P1", "P2", "P3")


def _fold_priority(value):
    """Fold a stray priority into the P0-P3 vocabulary; None if not recognisable."""
    v = (value or "").strip()
    if v in P_VOCABULARY:
        return v
    legacy = {k.lower(): p for k, p in LEGACY_PRIORITY_TO_P.items()}
    if v.lower() in legacy:
        return legacy[v.lower()]
    m = re.match(r"^P(\d+)(\.\d+)*$", v, re.IGNORECASE)
    if m:
        tier = min(int(m.group(1)), 3)
        return f"P{tier}"
    return None


def _doctor_rewrite(text):
    """Inside the --- frontmatter block: drop `status:`, fold `priority:`.

    Returns (new_text, changed, had_status, folded_priority). Only the
    frontmatter block is touched; body and other lines pass through exactly.
    """
    if not text.startswith("---"):
        return text, False, False, None
    end = text.find("\n---", 3)
    if end == -1:
        return text, False, False, None
    raw = text[3:end].strip("\n")
    body = text[end:]
    out_lines = []
    changed = False
    had_status = False
    folded = None
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if not m:
            out_lines.append(line)
            continue
        key, val = m.group(1), m.group(2).strip().strip("\"'")
        if key.lower() == "status":
            had_status = True
            changed = True
            continue  # drop the line — folder owns state
        if key.lower() == "priority" and val not in P_VOCABULARY:
            new_val = _fold_priority(val)
            if new_val and new_val != val:
                out_lines.append(f"priority: {new_val}")
                changed = True
                folded = new_val
                continue
        out_lines.append(line)
    new_text = "---\n" + "\n".join(out_lines) + body
    return new_text, changed, had_status, folded


def cmd_doctor(vault_path, fix=False):
    """Audit live files against the vault's own constitution.

    On a tree that declares a `block` bucket, `status:` in a live file is a
    violation and off-vocabulary `priority:` is a warning. With fix=True both
    are repaired in place. Archive buckets are never touched.

    Returns {"newvault": bool, "violations": [...], "warnings": [...], "fixed": [...]}.
    """
    tree = resolve_tree(vault_path)
    newvault = "block" in tree
    report = {"newvault": newvault, "violations": [], "warnings": [], "fixed": []}
    for bucket in hot_dirs(tree):
        root = os.path.join(vault_path, bucket)
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in sorted(files):
                if not fn.endswith(".md"):
                    continue
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, vault_path)
                try:
                    text = open(fp, "r", errors="replace").read()
                except OSError:
                    continue
                fields = plate_frontmatter(text)
                status_key = next((k for k in fields if k.lower() == "status"), None)
                priority = fields.get("priority")
                priority_off = newvault and priority is not None and priority not in P_VOCABULARY
                if not newvault:
                    continue  # legacy trees keep their filing conventions
                if fix:
                    if status_key is not None or priority_off:
                        new_text, changed, had_status, folded = _doctor_rewrite(text)
                        if changed and new_text != text:
                            with open(fp, "w") as f:
                                f.write(new_text)
                            parts = []
                            if had_status:
                                parts.append("stripped status:")
                            if folded:
                                parts.append(f"priority {priority} -> {folded}")
                            report["fixed"].append(f"{rel}: " + ", ".join(parts))
                else:
                    if status_key is not None:
                        report["violations"].append(
                            f"{rel}: status: field present — folder owns state (block tree)")
                    if priority_off:
                        fold = _fold_priority(priority)
                        hint = f" -> {fold}" if fold else " (no fold known)"
                        report["warnings"].append(
                            f"{rel}: priority {priority!r} off-vocabulary, expected P0-P3{hint}")
    return report


def cmd_help(subgroup=None):
    """Print the nested command reference (derived from COMMANDS.md).

    Works without a vault — pure static text, exits 0.
    Subgroups: None (top-level), "issue", "project", "context".
    """
    if subgroup == "issue":
        print("rvc issue — list, transition, and create issues")
        print()
        print("Usage:")
        print("  rvc issue list [⟨status|bucket⟩] [--dir ⟨bucket⟩]")
        print("  rvc issue ⟨ID⟩ ⟨action⟩ [--skip-ci]")
        print()
        print("Actions (valid set comes from the vault's tree in .rvc-root):")
        print("  triage        move to triage/next bucket")
        print("  start         move to active bucket")
        print("  block         move to blocked/decide bucket")
        print("  defer         move to deferred/parked bucket")
        print("  review        move to review bucket")
        print("  done          move to done bucket")
        print("  evict         move to archive/done")
        print("  supersede     move to archive/superseded")
        print("  create        create a new issue via the tree verb")
        print()
        print("Arguments:")
        print("  list          list issues; optional positional filters by status alias or bucket")
        print("                --dir <bucket>    list a specific configured bucket (e.g. --dir 30_ACTIVE)")
        print("  <ID> <action> transition the issue through the vault's tree (git mv + commit)")
        print("  --skip-ci     disable [skip ci] in commit message (default: enabled)")
        print()
        print("Note: viewing an issue is done with  rvc get <ID>  — the issue command")
        print("  handles listing and transitions only.")
    elif subgroup == "context":
        print("rvc context — assemble an issue's context (target + hard links + soft matches)")
        print()
        print("Usage:")
        print("  rvc context ⟨ID⟩ [--top-k ⟨N⟩] [--budget ⟨CHARS⟩] [--mode full|summary]")
        print("                   [--no-semantic] [--reindex]")
        print()
        print("Arguments:")
        print("  <ID>           issue or note id; unpadded resolves too (STORY-32 ≡ STORY-033)")
        print("  --top-k        semantic matches to retrieve (default: 3)")
        print("  --budget       total output character budget (default: 40000); over-budget")
        print("                 output drops the lowest-ranked items first, with a notice")
        print("  --mode         full text vs frontmatter+goal+AC summary (default: full)")
        print("  --no-semantic  resolve only explicit [[wikilinks]] (legacy behavior)")
        print("  --reindex      force a full rebuild of .rvc-context-cache.json")
        print()
        print("Note: the stdlib BM25 ranker indexes all .md files; archive buckets are")
        print("  indexed but never suggested, and the vault's knowledge dir ranks first.")
    elif subgroup == "project":
        print("rvc project — initialize a project with a vault subdirectory")
        print()
        print("Usage:")
        print("  rvc project init [⟨dir⟩] [--vault-name ⟨name⟩] [--tree legacy|newvault]")
        print("  rvc project info [⟨dir⟩]")
        print()
        print("Arguments:")
        print("  init           create a project with a vault subdirectory (not flat)")
        print("    <dir>            target directory (default: current)")
        print("    --vault-name     vault directory name (default: vault)")
        print("    --tree           bucket layout preset: legacy | newvault (default: legacy)")
        print("  info           print vault info and ROADMAP.md contents if present")
        print("    <dir>            project directory (default: current)")
        print()
        print("Note: 'rvc init' creates a flat vault directly; 'rvc project init' wraps it")
        print("  in a <vault-name>/ subdirectory. Use project init for multi-repo projects.")
    else:
        print("rvc — folder-as-state issue tracker & context engine")
        print()
        print("Usage:")
        print("  rvc [options] <command> [args...]")
        print()
        print("Options:")
        print("  --path <path>    project or vault path to operate on (default: .)")
        print()
        print("Commands:")
        print()
        print("  init [⟨dir⟩] [--tree legacy|newvault]")
        print("      Initialize a new flat vault (no vault/ subdirectory). Works without a vault.")
        print("      ⟨dir⟩        target directory (default: .)")
        print("      --tree       bucket layout preset (default: legacy)")
        print()
        print("  project")
        print("      Initialize a project with a vault subdirectory; or print vault info.")
        print("      Subcommands: init, info — use 'rvc project help' for details.")
        print()
        print("  install [--dir ⟨dir⟩] [--force] [--check]")
        print("      Install this script as 'rvc' on PATH (symlink). Works without a vault.")
        print("      --dir        install directory (default: ~/.local/bin)")
        print("      --force      overwrite an unrelated existing file at the target")
        print("      --check      verify installation and exit without changes")
        print()
        print("  create ⟨title⟩ [--prefix ⟨PREFIX⟩] [--type story|bug|task|epic]")
        print("             [--priority P0|P1|P2|P3|Low|Medium|High|Critical]")
        print("             [--body ⟨text⟩] [--dir ⟨bucket⟩] [--epic ⟨EPIC-XX⟩] [--skip-ci]")
        print("      Create a new issue: mints the next ID and lands in the create bucket.")
        print("      ⟨title⟩      issue title")
        print("      --prefix     ID prefix (default: STORY)")
        print("      --type       issue type (default: story)")
        print("      --priority   priority (default: Medium; newvault trees sort P0-P3)")
        print("      --body       initial issue body text")
        print("      --dir        destination bucket (default: this vault's create/triage bucket)")
        print("      --epic       parent epic name (e.g. EPIC-05)")
        print("      --skip-ci    disable [skip ci] in the commit message (default: enabled)")
        print()
        print("  issue")
        print("      Subcommands: list; ⟨ID⟩ ⟨action⟩ transitions — use 'rvc issue help'.")
        print("      Viewing an issue is done with 'rvc get ⟨ID⟩'.")
        print()
        print("  get ⟨ID⟩")
        print("      Print the raw issue file for ⟨ID⟩.")
        print("      ⟨ID⟩         issue id (e.g. STORY-032)")
        print()
        print("  context ⟨ID⟩ [--top-k ⟨N⟩] [--budget ⟨CHARS⟩] [--mode full|summary]")
        print("                [--no-semantic] [--reindex]")
        print("      Assemble context: target issue + explicit [[wikilinks]] + Top-K BM25 matches.")
        print("      ⟨ID⟩         issue id (e.g. STORY-032); unpadded STORY-32 also resolves")
        print("      --top-k      semantic matches to retrieve (default: 3)")
        print("      --budget     total output character budget (default: 40000)")
        print("      --mode       full text vs frontmatter+goal+AC summary (default: full)")
        print("      --no-semantic  resolve only explicit [[wikilinks]] (legacy behavior)")
        print("      --reindex    force a full rebuild of .rvc-context-cache.json")
        print()
        print("  list [⟨status⟩] [--dir ⟨bucket⟩]")
        print("      List issues (alias for 'rvc issue list').")
        print("      ⟨status⟩     filter by status alias or bucket (optional)")
        print("      --dir        list a specific configured bucket")
        print()
        print("  search ⟨query⟩")
        print("      Case-insensitive grep over every .md file in the vault.")
        print("      ⟨query⟩      search text")
        print()
        print("  plate [--as ⟨handle⟩] [--format text|json] [--stale-days ⟨N⟩]")
        print("      Render the plate: lanes computed from folders, priorities and open asks.")
        print("      --as         canonicalize this handle for the owed-turn lane")
        print("      --format     output format (default: text)")
        print("      --stale-days overdue threshold in days (default: 7)")
        print()
        print("  doctor [--fix]")
        print("      Audit the vault against its constitution (status:, priority vocabulary).")
        print("      --fix        strip status: and fold priorities in place")
        print("      Note: surgical repair; 'rescan' is the broader rewrite.")
        print()
        print("  rescan [--dry-run]")
        print("      Broad normalization: fix frontmatter, add wikilinks, infer tags,")
        print("      and rebuild .rvc-context-cache.json (the semantic context cache).")
        print("      --dry-run    show changes without writing")
        print("      Note: broader than 'doctor --fix' (constitution repair only).")
        print()
        print("  git-commit-all ⟨message⟩ [--dry-run] [--no-push] [--push]")
        print("      Commit across all dirty submodules plus the parent repo (safe incremental).")
        print("      --dry-run    show the plan without making changes")
        print("      --no-push    commit but do not push")
        print("      --push       commit and push (opt-in)")
        print()
        print("Commands that work without a vault: install, init, project init, help.")
        print()
        print("For command details, use 'rvc <command> help' or 'rvc <command> --help'.")
        print("Full reference: 10_CONTEXT/specs/COMMANDS.md (source of truth).")


def main():
    parser = argparse.ArgumentParser(description="RVC CLI - Vault Context Interface")
    parser.add_argument("--path", default=".", help="Path to project or vault")
    subparsers = parser.add_subparsers(dest="command")

    get_p = subparsers.add_parser("get")
    get_p.add_argument("id")

    context_p = subparsers.add_parser("context")
    context_p.add_argument("id")
    context_p.add_argument("--top-k", type=int, default=CONTEXT_DEFAULT_TOP_K,
                           help="Semantic/BM25 matches to retrieve (default: 3)")
    context_p.add_argument("--budget", type=int, default=CONTEXT_DEFAULT_BUDGET,
                           help="Total output character budget (default: 40000)")
    context_p.add_argument("--mode", choices=("full", "summary"), default="full",
                           help="full text vs frontmatter+goal+AC summary (default: full)")
    context_p.add_argument("--no-semantic", action="store_true", dest="no_semantic",
                           help="Resolve only explicit [[wikilinks]] (legacy behavior)")
    context_p.add_argument("--reindex", action="store_true",
                           help="Force a full rebuild of .rvc-context-cache.json")

    issue_p = subparsers.add_parser("issue")
    issue_p.add_argument("action_or_id")
    issue_p.add_argument("action_or_status", nargs="?")
    issue_p.add_argument("--dir", dest="list_dir", default=None,
                         help="List a specific configured bucket (e.g. --dir 30_ACTIVE)")
    issue_p.add_argument("--skip-ci", action="store_false", dest="skip_ci", default=True,
                         help="Disable [skip ci] in commit message (default: enabled)")

    list_p = subparsers.add_parser("list", help="List issues (alias for `issue list`)")
    list_p.add_argument("status", nargs="?", default=None)
    list_p.add_argument("--dir", dest="list_dir", default=None,
                        help="List a specific configured bucket (e.g. --dir 20_NEXT)")

    plate_p = subparsers.add_parser(
        "plate", help="Render the plate: lanes computed from folders, priorities and open asks"
    )
    plate_p.add_argument("--as", dest="as_alias", default=None,
                         help="Canonicalize this handle for the owed-turn lane (e.g. --as D). "
                              "Omit it for an identity-free render (tree lanes only).")
    plate_p.add_argument("--format", choices=("text", "json"), default="text")
    plate_p.add_argument("--stale-days", type=int, default=7,
                         help="Overdue threshold in days without a new section (default: 7)")

    create_p = subparsers.add_parser("create", help="Create a new issue")
    create_p.add_argument("title", help="Issue title")
    create_p.add_argument("--prefix", default="STORY", help="ID prefix (default: STORY)")
    create_p.add_argument("--type", default="story", dest="issue_type",
                          choices=["story", "bug", "task", "epic"],
                          help="Issue type (default: story)")
    create_p.add_argument(
        "--priority",
        default="Medium",
        choices=["P0", "P1", "P2", "P3", "Low", "Medium", "High", "Critical"],
        help="Priority (default: Medium). newvault trees sort P0-P3 (ADLAI ROUTING §5.3);"
        " the legacy names remain accepted for vaults that still use them.",
    )
    create_p.add_argument("--body", default="", help="Initial issue body text")
    create_p.add_argument("--dir", default=None, dest="directory",
                          help="Bucket for the new issue (default: this vault's inbox/triage bucket)")
    create_p.add_argument("--epic", default="", help="Parent epic name (e.g. EPIC-05-PRD-Phase-2)")
    create_p.add_argument("--skip-ci", action="store_false", dest="skip_ci", default=True,
                          help="Disable [skip ci] in commit message (default: enabled)")

    search_p = subparsers.add_parser("search", help="Search vault files")
    search_p.add_argument("query", help="Search query (case-insensitive)")

    commit_p = subparsers.add_parser("git-commit-all", help="Commit across all dirty submodules + parent repo (safe incremental)")
    commit_p.add_argument("message", help="Commit message (e.g. 'feat: something (STORY-XX)')")
    commit_p.add_argument("--dry-run", action="store_true", help="Show plan without making changes")
    commit_p.add_argument("--no-push", action="store_true", help="Commit but do not push")
    commit_p.add_argument("--push", action="store_true", help="Commit and push (opt-in)")

    rescan_p = subparsers.add_parser("rescan", help="Rescan vault: fix frontmatter, add wikilinks")
    rescan_p.add_argument("--dry-run", action="store_true", help="Show what would change without writing")

    doctor_p = subparsers.add_parser(
        "doctor",
        help="Audit the vault against its own constitution (status:, priority vocabulary)")
    doctor_p.add_argument("--fix", action="store_true",
                          help="Strip status: and fold priorities in place (block-bucket trees)")

    init_p = subparsers.add_parser("init", help="Initialize a new vault (flat — no vault/ subdirectory)")
    init_p.add_argument("target_path", nargs="?", default=".", help="Directory to initialize (default: current)")
    init_p.add_argument("--tree", choices=["legacy", "newvault"], default="legacy",
                        help="Vault tree preset (default: legacy)")

    project_p = subparsers.add_parser("project")
    project_p.add_argument("action", choices=["init", "info", "help"])
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

    help_p = subparsers.add_parser(
        "help",
        help="Show this nested command reference (works without a vault)")
    help_p.add_argument("subgroup", nargs="?", default=None,
                        help="Command group: issue, project, context (default: top level)")

    args = parser.parse_args()

    # Help needs no vault — pure static text, always exits 0 (AC4).
    if args.command == "help":
        cmd_help(args.subgroup)
        return
    if args.command == "issue" and args.action_or_id == "help":
        cmd_help("issue")
        return
    if args.command == "project" and args.action == "help":
        cmd_help("project")
        return

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
        cmd_context(vault_root, args.id, top_k=args.top_k, budget=args.budget,
                    mode=args.mode, no_semantic=args.no_semantic, reindex=args.reindex)
    elif args.command == "issue":
        if args.action_or_id == "list":
            cmd_issue_list(vault_root, args.action_or_status, list_dir=args.list_dir)
        else:
            if not args.action_or_status:
                cmd_get(vault_root, args.action_or_id)
            else:
                cmd_issue_action(vault_root, args.action_or_id, args.action_or_status, skip_ci=args.skip_ci)
    elif args.command == "list":
        cmd_issue_list(vault_root, args.status, list_dir=args.list_dir)
    elif args.command == "plate":
        cmd_plate(vault_root, as_alias=args.as_alias, fmt=args.format, stale_days=args.stale_days)
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
            skip_ci=args.skip_ci,
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
        if rc == 0 and not getattr(args, "dry_run", False):
            # Full reconciliation of the semantic context cache (STORY-033).
            context_cache_update(vault_root, force=True)
            print(f"[RVC] Context cache rebuilt: {CONTEXT_CACHE_NAME}")
    elif args.command == "doctor":
        report = cmd_doctor(vault_root, fix=args.fix)
        for v in report["violations"]:
            print(f"[doctor] VIOLATION: {v}")
        for w in report["warnings"]:
            print(f"[doctor] warning:   {w}")
        for fx in report["fixed"]:
            print(f"[doctor] fixed:     {fx}")
        if report["violations"]:
            print(f"[doctor] {len(report['violations'])} violation(s) found — "
                  f"run `rvc doctor --fix` on a block-bucket tree")
            sys.exit(1)
        if report["newvault"]:
            print(f"[doctor] OK — {len(report['fixed'])} fixed, "
                  f"{len(report['warnings'])} warning(s), 0 violations")
        else:
            print("[doctor] OK — legacy tree (no block bucket); status/priority conventions untouched")
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
