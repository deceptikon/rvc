#!/usr/bin/env python3
"""`rvc init` / `rvc project init` provision a vault-level .gitignore.

Every vault must ignore RVC's lock file (and Obsidian volatile state) in its
host repo — otherwise `.rvc-create.lock` shows up as untracked noise in every
project that hosts a vault. The helper must be idempotent and non-clobbering.
"""

import os
import tempfile

import helpers
from helpers import make_vault, rvc_cli


def test_write_vault_gitignore_creates_file_with_lock_rule():
    _, vault = make_vault()
    rvc_cli._write_vault_gitignore(vault)
    content = open(os.path.join(vault, ".gitignore")).read()
    assert ".rvc-create.lock" in content
    assert "**/.obsidian/workspace.json" in content


def test_write_vault_gitignore_is_idempotent():
    _, vault = make_vault()
    rvc_cli._write_vault_gitignore(vault)
    first = open(os.path.join(vault, ".gitignore")).read()
    rvc_cli._write_vault_gitignore(vault)
    second = open(os.path.join(vault, ".gitignore")).read()
    assert first == second
    assert second.count(".rvc-create.lock") == 1


def test_write_vault_gitignore_preserves_existing_content():
    _, vault = make_vault()
    path = os.path.join(vault, ".gitignore")
    with open(path, "w") as f:
        f.write("node_modules/\n*.log\n")
    rvc_cli._write_vault_gitignore(vault)
    content = open(path).read()
    assert "node_modules/" in content
    assert "*.log" in content
    assert ".rvc-create.lock" in content


def test_write_vault_gitignore_covers_context_cache():
    """STORY-033 AC2: the semantic context cache is never tracked."""
    _, vault = make_vault()
    rvc_cli._write_vault_gitignore(vault)
    content = open(os.path.join(vault, ".gitignore")).read()
    assert ".rvc-context-cache.json" in content


def test_cmd_init_provisions_vault_gitignore():
    """End-to-end: a fresh `rvc init` leaves the lock rule in the vault."""
    root = tempfile.mkdtemp(prefix="rvc-init-")
    rvc_cli.cmd_init(root, "newvault")
    content = open(os.path.join(root, ".gitignore")).read()
    assert ".rvc-create.lock" in content
    assert ".rvc-context-cache.json" in content
