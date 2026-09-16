#!/usr/bin/env python3
"""Shared fixtures for the RVC local test suite.

Loads rvc-cli.py in-process so tests can call its functions directly without
subprocess overhead or shell quirks. Scratch vaults are tempdirs with a
newvault `.rvc-root` tree; they deliberately contain no `.git`, so
`sync_after` / `find_git_root` no-op (no commits happen in tests).
"""

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "rvc-cli.py"

# Force OS temp under the approved scratch location (RVC tests must never touch
# a real vault).
os.environ.setdefault("TMPDIR", "/tmp/opencode")
tempfile.tempdir = "/tmp/opencode"


def _load_cli():
    spec = importlib.util.spec_from_file_location("rvc_cli", CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_restructure():
    spec = importlib.util.spec_from_file_location("vault_restructure", REPO_ROOT / "vault-restructure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rvc_cli = _load_cli()
vault_restructure = _load_restructure()

NEWVAULT_TREE = {
    "create": "00_INBOX",
    "triage": "20_NEXT",
    "start": "30_ACTIVE",
    "block": "40_DECIDE",
    "defer": "50_DEFERRED",
    "done": "60_DONE",
    "evict": "90_ARCHIVE/done",
    "supersede": "90_ARCHIVE/superseded",
}


def make_vault():
    """Create a scratch newvault tree; returns (tmpdir_path, vault_path)."""
    root = tempfile.mkdtemp(prefix="rvc-test-")
    vault = os.path.join(root, "vault")
    os.makedirs(vault)
    with open(os.path.join(vault, ".rvc-root"), "w") as f:
        f.write("vault=scratch\n")
        for verb, directory in sorted(NEWVAULT_TREE.items()):
            f.write(f"tree.{verb}={directory}\n")
    for directory in set(NEWVAULT_TREE.values()):
        os.makedirs(os.path.join(vault, directory), exist_ok=True)
    return root, vault


def write_issue(vault, rel_path, frontmatter, body=""):
    """Write an issue file under the vault with the given frontmatter dict."""
    path = os.path.join(vault, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    if body:
        lines.append(body)
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def read_frontmatter(path):
    """Minimal key:value frontmatter reader (mirrors rvc_cli.plate_frontmatter)."""
    return rvc_cli.plate_frontmatter(open(path).read())


def capture_stdout(fn, *args, **kwargs):
    """Run fn(*args, **kwargs) with stdout captured; returns (return, output)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ret = fn(*args, **kwargs)
    return ret, buf.getvalue()


def plate_json(vault, **kwargs):
    """Run cmd_plate(fmt='json') and return the parsed payload dict."""
    kwargs.setdefault("fmt", "json")
    kwargs.setdefault("today", None)
    _, out = capture_stdout(rvc_cli.cmd_plate, vault, **kwargs)
    return json.loads(out)