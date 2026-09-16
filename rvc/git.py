"""Git repository synchronization and submodule multi-commit automation."""

import os
import sys
import configparser
from rvc.core import run_cmd, find_git_root


def sync_before(vault_path):
    git_root = find_git_root(vault_path)
    if git_root:
        print("[RVC] Synchronizing state (git pull --rebase)...")
        rc, out, err = run_cmd("git pull --rebase", cwd=git_root)
        if rc != 0:
            print(f"[RVC] Warning: Git pull failed:\n{err}")


def _push_enabled(vault_path):
    """Push is OPT-IN. Enabled only by env `RVC_PUSH=1` or `.rvc-root` line `push=true`."""
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
        if skip_ci:
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


def _parse_gitmodules(repo_root):
    """Parse .gitmodules and return {path: url} for all submodules."""
    modules_path = os.path.join(repo_root, ".gitmodules")
    if not os.path.exists(modules_path):
        return {}
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
        return
    for branch in ["main", "master"]:
        rc2, _, _ = run_cmd(f"git show-ref --verify refs/heads/{branch}", cwd=repo_path)
        if rc2 == 0:
            run_cmd(f"git checkout -B {branch} HEAD", cwd=repo_path)
            print(f"[git-commit-all]   {label}Moved detached HEAD to branch '{branch}'")
            return
    run_cmd("git checkout -b main", cwd=repo_path)
    print(f"[git-commit-all]   {label}Created branch 'main' at detached HEAD")


def cmd_git_commit_all(vault_path, message, dry_run=False, no_push=False, push=False):
    """Commit across all dirty submodules, then in parent repo. Safe incremental."""
    if not dry_run and not no_push and not push:
        print("[git-commit-all] Error: Specify --dry-run, --no-push, or --push")
        sys.exit(1)

    git_root = find_git_root(vault_path)
    if not git_root:
        print("[git-commit-all] Error: No git root found.")
        sys.exit(1)

    dirty = _find_dirty_submodules(git_root)

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
            has_parent_changes = True
            parent_staged = ""
            parent_unstaged = ""

    if dry_run:
        if not dirty and not has_parent_changes:
            return
        rc_ps2, out_ps2, _ = run_cmd("git diff --cached --stat", cwd=git_root)
        rc_pu2, out_pu2, _ = run_cmd("git diff --stat", cwd=git_root)
        pst = out_ps2.strip()
        pun = out_pu2.strip()
        if has_parent_changes and not (pst or pun):
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
