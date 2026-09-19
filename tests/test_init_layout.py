#!/usr/bin/env python3
"""STORY-037: `rvc init` — named vault subdir (default 0-vault), marker +
.gitignore at the project root, idempotent additive re-runs, and vault
resolution under the new layout.

Acceptance criteria under test:
- AC1: 0-vault/ structure; marker + gitignore at project root; links + README
  at project root; nothing inside the vault besides buckets/ROUTING.
- AC2: second run is additive — no duplicate marker/gitignore lines, existing
  ROUTING kept verbatim, user marker lines preserved.
- AC3: find_vault_root resolves the descended vault from the project root and
  from inside the vault.
- AC4: old layouts still resolve — flat markers (no vault=) and self-referential
  inner markers (vault=scratch) return the same vault as before.
- AC6: config readers (tree, plate, push, feedback) resolve the project-root
  marker; the automatic feedback config lands there, never inside the vault.
"""

import os
import tempfile

import helpers
import helpers
from helpers import make_vault, rvc_cli

NEWVAULT_DIRS = {
    "00_INBOX", "10_CONTEXT", "20_NEXT", "30_ACTIVE", "40_DECIDE",
    "50_DEFERRED", "60_DONE", "90_ARCHIVE",
}


def fresh_root():
    return tempfile.mkdtemp(prefix="rvc-init-layout-")


def test_init_creates_0_vault_layout():
    root = fresh_root()
    rvc_cli.cmd_init(root)

    vault = os.path.join(root, "0-vault")
    assert os.path.isdir(vault)
    for d in NEWVAULT_DIRS:
        assert os.path.isdir(os.path.join(vault, d)), f"missing bucket {d}"
    assert os.path.isdir(os.path.join(vault, ".obsidian"))
    assert os.path.isfile(os.path.join(vault, "10_CONTEXT", "ROUTING.md"))
    # no marker inside the vault
    assert not os.path.exists(os.path.join(vault, ".rvc-root"))

    # marker + gitignore at the project root, outside the vault
    marker = open(os.path.join(root, ".rvc-root")).read()
    assert "vault=0-vault" in marker
    assert "tree.create=00_INBOX" in marker
    assert "tree.roadmap=10_CONTEXT" in marker
    gitignore = open(os.path.join(root, ".gitignore")).read()
    assert ".rvc-create.lock" in gitignore
    assert ".rvc-context-cache.json" in gitignore

    # links + README at the project root
    target = os.path.realpath(os.path.join(vault, "10_CONTEXT", "ROUTING.md"))
    assert os.path.islink(os.path.join(root, "AGENTS.md"))
    assert os.path.realpath(os.path.join(root, "AGENTS.md")) == target
    assert os.path.isfile(os.path.join(root, "README.md"))


def test_init_custom_vault_name():
    root = fresh_root()
    rvc_cli.cmd_init(root, "rvc-vault")
    assert os.path.isdir(os.path.join(root, "rvc-vault", "00_INBOX"))
    marker = open(os.path.join(root, ".rvc-root")).read()
    assert "vault=rvc-vault" in marker


def test_init_rerun_is_additive_and_converges():
    root = fresh_root()
    routing = os.path.join(root, "0-vault", "10_CONTEXT", "ROUTING.md")
    rvc_cli.cmd_init(root)
    with open(routing, "w") as f:
        f.write("# Vault Routing\n\nCustom constitution content.\n")

    rvc_cli.cmd_init(root)  # second run: no re-prompt (non-tty), no overwrite

    # routing content untouched
    assert "Custom constitution content." in open(routing).read()
    # no duplicate marker lines: each tree key appears exactly once
    marker = open(os.path.join(root, ".rvc-root")).read()
    for verb in ("create", "triage", "start", "done"):
        assert marker.count(f"tree.{verb}=") == 1, f"duplicate tree.{verb}= in marker"
    assert marker.count("vault=") == 1
    # gitignore appended, not duplicated
    git = open(os.path.join(root, ".gitignore")).read()
    assert git.count(".rvc-create.lock") == 1


def test_init_preserves_user_marker_lines():
    root = fresh_root()
    with open(os.path.join(root, ".rvc-root"), "w") as f:
        f.write("feedback.to=/somewhere/rvc-vault\npush=true\n")
    rvc_cli.cmd_init(root)
    marker = open(os.path.join(root, ".rvc-root")).read()
    assert "feedback.to=/somewhere/rvc-vault" in marker
    assert "push=true" in marker
    assert "vault=0-vault" in marker
    assert "tree.create=00_INBOX" in marker


def test_find_vault_root_descends_via_vault():
    root = fresh_root()
    rvc_cli.cmd_init(root)
    vault = os.path.join(root, "0-vault")
    assert rvc_cli.find_vault_root(root) == vault
    assert rvc_cli.find_vault_root(os.path.join(vault, "20_NEXT")) == vault


def test_init_refuses_second_vault_when_inner_vault_exists():
    """A repo that already owns a vault via an inner self-referential marker
    (legacy dogfooding layout: `rvc-vault/.rvc-root` → `vault=rvc-vault`) must
    not get a second vault scaffolded beside it — no 0-vault, no root marker.
    """
    root = fresh_root()
    inner = os.path.join(root, "rvc-vault")
    os.makedirs(os.path.join(inner, "10_CONTEXT"))
    with open(os.path.join(inner, ".rvc-root"), "w") as f:
        f.write("vault=rvc-vault\n")
        for verb, directory in sorted(helpers.NEWVAULT_TREE.items()):
            f.write(f"tree.{verb}={directory}\n")

    assert rvc_cli.cmd_init(root) == root
    # no second vault, no root marker, inner vault untouched
    assert not os.path.isdir(os.path.join(root, "0-vault"))
    assert not os.path.isfile(os.path.join(root, ".rvc-root"))
    assert os.path.isfile(os.path.join(root, "rvc-vault", ".rvc-root"))


def test_find_vault_root_accepts_file_paths():
    """A file inside a new-layout vault resolves to that vault (no NotADirectory
    on os.listdir — feedback letters are handed to find_vault_root as files)."""
    root = fresh_root()
    rvc_cli.cmd_init(root)
    vault = os.path.join(root, "0-vault")
    letter = os.path.join(vault, "00_INBOX", "FEEDBACK-rvc.md")
    os.makedirs(os.path.dirname(letter), exist_ok=True)
    with open(letter, "w") as f:
        f.write("# FEEDBACK-rvc\n")
    assert rvc_cli.find_vault_root(letter) == vault


def test_find_vault_root_keeps_flat_and_self_ref_markers():
    # flat marker (no vault= line) stays put
    flat = tempfile.mkdtemp(prefix="rvc-flat-")
    with open(os.path.join(flat, ".rvc-root"), "w") as f:
        f.write("tree.create=00_INBOX\n")
    assert rvc_cli.find_vault_root(flat) == flat

    # self-referential inner marker (make_vault style) stays put
    _, vault = make_vault()
    assert rvc_cli.find_vault_root(vault) == vault


def test_init_on_flat_vault_is_noop():
    root = tempfile.mkdtemp(prefix="rvc-flat-init-")
    with open(os.path.join(root, ".rvc-root"), "w") as f:
        f.write("tree.create=00_INBOX\n")
    rvc_cli.cmd_init(root)
    # nothing nested inside the flat vault
    assert not os.path.isdir(os.path.join(root, "0-vault"))
    marker = open(os.path.join(root, ".rvc-root")).read()
    assert "vault=" not in marker


def test_config_and_push_resolve_project_marker():
    root = fresh_root()
    rvc_cli.cmd_init(root)
    vault = os.path.join(root, "0-vault")

    tree = rvc_cli.resolve_tree(vault)
    assert tree["create"] == "00_INBOX"

    _, owner, sources, _ = rvc_cli.read_plate_config(vault)
    assert owner is None and sources == {}

    # push opt-in read from the project-root marker
    with open(os.path.join(root, ".rvc-root"), "a") as f:
        f.write("push=true\n")
    assert rvc_cli._push_enabled(vault) is True


def test_feedback_config_writes_project_root_marker():
    root = fresh_root()
    rvc_cli.cmd_init(root)
    vault = os.path.join(root, "0-vault")
    target = tempfile.mkdtemp(prefix="rvc-target-")
    added = rvc_cli._ensure_feedback_config(vault, target)
    assert added
    marker = open(os.path.join(root, ".rvc-root")).read()
    assert f"feedback.to={os.path.abspath(target)}" in marker
    assert f"plate.source.rvc={os.path.abspath(target)}" in marker
    assert "plate.alias.rvc=F" in marker
    # nothing written inside the vault — marker stays at the project root
    assert not os.path.exists(os.path.join(vault, ".rvc-root"))