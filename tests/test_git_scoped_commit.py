#!/usr/bin/env python3
"""STORY-034 AC2: transition/create commits are scoped and never sweep an index.

The old `sync_after` ran a bare `git commit` after `git add` of its own paths,
so any files the operator had already staged were silently swept into the RVC
commit message. The rework commits from a temporary index seeded from HEAD that
contains ONLY the moved/created paths.

These tests build a real git repo (a scratch vault with no remote), stage
operator-owned work, then run `rvc create` and a transition — and assert the RVC
commits touch exactly one path while the operator's staged file is untouched.
"""

import os
import subprocess

import helpers
from helpers import make_vault, rvc_cli, write_issue


def git(root, *args):
    return subprocess.run(
        ["git", "-C", root, *args], capture_output=True, text=True
    )


def make_vault_with_git():
    """Scratch vault inside a fresh git repo with a committed baseline."""
    root, vault = make_vault()
    git(root, "init", "-q", ".")
    git(root, "config", "user.email", "test@rvc")
    git(root, "config", "user.name", "RVC test")
    git(root, "add", "-A")
    res = git(root, "commit", "-qm", "baseline")
    assert res.returncode == 0, res.stderr
    return root, vault


def test_create_commit_is_scoped_and_leaves_operator_staging():
    """AC2: `rvc create` commits only the new file; the operator's staged work survives."""
    root, vault = make_vault_with_git()
    staged = os.path.join(root, "unrelated.txt")
    with open(staged, "w") as f:
        f.write("operator work\n")
    git(root, "add", "--", "unrelated.txt")

    _, out = helpers.capture_stdout(
        rvc_cli.cmd_create_issue, vault, "Scoped Probe", priority="P1")
    assert "Committing state" in out

    stat = git(root, "show", "--stat", "--oneline", "HEAD").stdout
    assert "STORY-01-Scoped-Probe.md" in stat
    assert "unrelated.txt" not in stat, "operator's staged file was swept into the RVC commit!"

    staged_now = git(root, "diff", "--cached", "--name-only").stdout.splitlines()
    assert "unrelated.txt" in staged_now, "operator's staging must survive the RVC commit"
    # The new issue file must be tracked AND clean in the real index (only the
    # operator's own staged file may remain in the status).
    assert "STORY-01" not in git(root, "status", "--short").stdout, (
        "rvc-owned paths must be clean after the commit; got:\n"
        + git(root, "status", "--short").stdout)


def test_transition_commit_is_scoped_and_records_the_rename():
    """AC2: a triage transition commits as a rename of only the moved path."""
    root, vault = make_vault_with_git()
    issue = write_issue(vault, "00_INBOX/STORY-07-Probe.md",
                        {"id": "STORY-07", "type": "story", "priority": "P1"})
    git(root, "add", "-A")
    git(root, "commit", "-qm", "seed STORY-07")

    staged = os.path.join(root, "unrelated.txt")
    with open(staged, "w") as f:
        f.write("operator work\n")
    git(root, "add", "--", "unrelated.txt")

    _, out = helpers.capture_stdout(
        rvc_cli.cmd_issue_action, vault, "STORY-07", "triage")
    assert "Committing state" in out

    stat = git(root, "show", "--stat", "--oneline", "HEAD").stdout
    assert "STORY-07-Probe.md" in stat
    assert "unrelated.txt" not in stat, "operator's staged file was swept into the transition commit!"
    moved = os.path.join(vault, "20_NEXT", "STORY-07-Probe.md")
    assert os.path.exists(moved)

    # The rename must be committed — no lingering staged rename for rvc's path.
    staged_now = git(root, "diff", "--cached", "--name-only").stdout.splitlines()
    assert "unrelated.txt" in staged_now
    assert "STORY-07-Probe.md" not in staged_now, (
        "the rename must be committed, not left staged:\n" + "\n".join(staged_now))
    # rvc-owned paths clean; only the operator's staged file may remain staged.
    assert "STORY-07" not in git(root, "status", "--short").stdout, (
        "rvc-owned paths must be clean after the transition commit; got:\n"
        + git(root, "status", "--short").stdout)