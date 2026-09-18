#!/usr/bin/env python3
"""STORY-129/137: transitions on never-committed issue files are calm.

An untracked deposit (a `??` file under 20_NEXT) used to cascade three scary
warnings — the pull-abort on unrelated unstaged WIP, `git mv failed (fatal:
not under version control)`, then `could not stage <old path>` — before
landing the move. Now the pull is skipped when the tree is dirty, untracked
sources take a plain move with a friendly note, and nothing tries to
`rm --cached` a path that was never tracked.
"""

import contextlib
import io
import os
import subprocess
import tempfile

from helpers import NEWVAULT_TREE, rvc_cli


def _git(root, *args):
    return subprocess.run(["git", "-C", root, *args],
                          capture_output=True, text=True)


def _init_git_vault():
    """Scratch newvault inside a fresh git repo with a committed baseline."""
    root = tempfile.mkdtemp(prefix="rvc-git-test-", dir="/tmp/opencode")
    vault = os.path.join(root, "vault")
    os.makedirs(vault)
    with open(os.path.join(vault, ".rvc-root"), "w") as f:
        f.write("vault=git-scratch\n")
        for verb, directory in sorted(NEWVAULT_TREE.items()):
            f.write(f"tree.{verb}={directory}\n")
    for directory in set(NEWVAULT_TREE.values()):
        os.makedirs(os.path.join(vault, directory), exist_ok=True)
    res = _git(root, "init", "-q")
    assert res.returncode == 0, res.stderr
    _git(root, "config", "user.email", "rvc-test@example.com")
    _git(root, "config", "user.name", "RVC Test")
    res = _git(root, "add", "-A")
    assert res.returncode == 0, res.stderr
    res = _git(root, "commit", "-qm", "baseline [skip ci]")
    assert res.returncode == 0, res.stderr
    return root, vault


def _write_issue(vault, rel, issue_id):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f"---\nid: {issue_id}\ntype: story\npriority: P1\n---\n\n"
                f"# {issue_id}\n")
    return path


def run_action(vault, issue_id, action):
    """Call cmd_issue_action capturing stdout+stderr; returns (rc, out, err)."""
    out_buf, err_buf = io.StringIO(), io.StringIO()
    rc = 0
    try:
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            rvc_cli.cmd_issue_action(vault, issue_id, action)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
    return rc, out_buf.getvalue(), err_buf.getvalue()


def test_start_on_untracked_issue_is_calm():
    """Untracked source: plain move, no git fatals, no pull abort — and committed."""
    root, vault = _init_git_vault()
    src = _write_issue(vault, "20_NEXT/STORY-99-Untracked.md", "STORY-99")

    rc, out, err = run_action(vault, "STORY-99", "start")

    assert rc == 0, f"start must succeed: {err!r}"
    assert not os.path.exists(src), "source must move"
    moved = os.path.join(vault, "30_ACTIVE", "STORY-99-Untracked.md")
    assert os.path.exists(moved), "issue must land in 30_ACTIVE"

    low = (out + err).lower()
    assert "cannot pull with rebase" not in low, f"raw pull-abort leaked:\n{out}\n{err}"
    assert "git mv failed" not in out, f"raw git-mv fatal leaked:\n{out}"
    assert "could not stage" not in out, f"raw rm --cached fatal leaked:\n{out}"
    assert "untracked" in low, f"friendly plain-move note missing:\n{out}"

    tracked = _git(root, "ls-files", "--error-unmatch", "--",
                   "vault/30_ACTIVE/STORY-99-Untracked.md").returncode
    assert tracked == 0, "the transition must commit the moved file"
    # rvc-owned paths clean; nothing staged/left over.
    status = _git(root, "status", "--short").stdout.strip()
    assert status == "", f"working tree must be clean after transition, got:\n{status}"


def test_done_on_untracked_issue_is_calm():
    """`done` on a never-committed file is equally quiet (STORY-137 2nd repro)."""
    _, vault = _init_git_vault()
    src = _write_issue(vault, "30_ACTIVE/STORY-98-Untracked.md", "STORY-98")

    rc, out, err = run_action(vault, "STORY-98", "done")

    assert rc == 0, f"done must succeed: {err!r}"
    assert not os.path.exists(src)
    moved = os.path.join(vault, "60_DONE", "STORY-98-Untracked.md")
    assert os.path.exists(moved)
    low = (out + err).lower()
    assert "cannot pull with rebase" not in low
    assert "git mv failed" not in out
    assert "could not stage" not in out


def test_start_on_tracked_issue_still_uses_git_mv():
    """Regression: a tracked source still records a git rename, no untracked note."""
    root, vault = _init_git_vault()
    src = _write_issue(vault, "20_NEXT/STORY-97-Tracked.md", "STORY-97")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed tracked issue [skip ci]")

    rc, out, err = run_action(vault, "STORY-97", "start")

    assert rc == 0, f"start must succeed: {err!r}"
    moved = os.path.join(vault, "30_ACTIVE", "STORY-97-Tracked.md")
    assert os.path.exists(moved)
    assert not os.path.exists(src), "tracked source must be gone"
    assert "untracked" not in (out + err).lower(), \
        f"tracked source must not get the untracked note:\n{out}\n{err}"

    # The move must be committed as a rename: old path gone from HEAD, new path present.
    show = _git(root, "show", "--stat", "--oneline", "HEAD").stdout
    assert "STORY-97-Tracked.md" in show
    gone = _git(root, "cat-file", "-e", "HEAD:vault/20_NEXT/STORY-97-Tracked.md").returncode
    assert gone != 0, "old path must not survive in HEAD after a rename commit"
    status = _git(root, "status", "--short").stdout.strip()
    assert status == "", f"working tree must be clean after transition, got:\n{status}"


def test_sync_before_skips_pull_when_tree_dirty():
    """Dirty tree: sync_before must not attempt (or fail) a pull --rebase."""
    _, vault = _init_git_vault()
    with open(os.path.join(vault, "20_NEXT/STORY-96-Wip.md"), "w") as f:
        f.write("---\nid: STORY-96\ntype: story\npriority: P1\n---\n\n# STORY-96\n")

    out_buf = io.StringIO()
    with contextlib.redirect_stdout(out_buf):
        rvc_cli.sync_before(vault)

    out = out_buf.getvalue()
    assert "pull --rebase" in out, f"expected the skip notice, got:\n{out}"
    assert "cannot pull with rebase" not in out