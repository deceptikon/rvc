"""External feedback ingest: `rvc feedback @<file>`.

A client vault (ADLAI, conductor, dash, ...) reports tool friction by dropping a
letter in its inbox (e.g. `00_INBOX/FEEDBACK-rvc.md`). This command moves the
letter into the RVC vault as a regular `BUG-<n>` issue — same lifecycle buckets,
same verbs — records the submitter in frontmatter (`origin:`), removes the
source letter on the client side, and prints the submitter's dashboard line.

BUG- is deliberately NOT a parallel type: `bug` already gates into triage and
plate with zero registration (STORY-036). Any display alias (a client shows
`BUG-14` as `F-14`) is a rendering concern owned by the plate lane
(`plate.alias.<name>=F`), never the record.
"""

import datetime
import os
import re
import sys

from rvc.core import (
    find_git_root, find_vault_root, resolve_tree, _next_id,
    vault_create_lock, run_cmd,
)
from rvc.git import sync_after, is_tracked
from rvc.issues import _sanitize_filename

_BUG_ID_RE = re.compile(r"^(BUG-\d+)")


def _feedback_target(vault_path, explicit):
    """Where feedback ingests: `--to` wins, then `feedback.to=` in .rvc-root, then env."""
    if explicit:
        return os.path.abspath(explicit)
    root_file = os.path.join(vault_path, ".rvc-root")
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("feedback.to="):
                    value = line[len("feedback.to="):].strip()
                    if value:
                        return os.path.abspath(value)
    env = os.environ.get("RVC_FEEDBACK_TO", "").strip()
    if env:
        return os.path.abspath(env)
    return None


def _feedback_title(text):
    """Derive a title from the letter: its first H1, else its first non-blank line."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            return stripped[2:].strip()[:80] or None
        return stripped[:80]
    return None


def _bug_counts(vault_path):
    """Classify BUG-* items by lifecycle: (pending IDs sorted, done count)."""
    tree = resolve_tree(vault_path)
    pending_dirs = {tree.get(k) for k in ("create", "triage", "start", "block", "defer") if tree.get(k)}
    done_dirs = {tree.get(k) for k in ("done", "evict", "supersede") if tree.get(k)}
    pending, done = [], 0
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            m = _BUG_ID_RE.match(fname)
            if not m:
                continue
            rel = os.path.relpath(root, vault_path).replace(os.sep, "/")
            path = f"{rel}/{fname}" if rel != "." else fname
            if any(path.startswith(d + "/") for d in done_dirs):
                done += 1
            elif any(path.startswith(d + "/") for d in pending_dirs):
                pending.append(m.group(1))
    pending.sort(key=lambda i: int(i.split("-")[1]))
    return pending, done


def _release_source(src, issue_id, origin):
    """Move the letter out of the client repo: git rm+commit when tracked, else plain delete."""
    git_root = find_git_root(src)
    if not git_root:
        try:
            os.remove(src)
        except OSError as e:
            return f"Warning: could not remove source ({e}); remove it by hand."
        return "Source removed (client dir has no git)."
    if not is_tracked(git_root, src):
        try:
            os.remove(src)
        except OSError as e:
            return f"Warning: could not remove source ({e}); remove it by hand."
        return "Source removed (was untracked)."
    rel = os.path.relpath(os.path.abspath(src), git_root)
    rc, _, err = run_cmd(f"git rm -q -- '{src}'", cwd=git_root)
    if rc != 0:
        return f"Warning: could not `git rm` {rel}: {err.strip()} — remove it by hand."
    rc, _, err = run_cmd(
        f"git commit -qm 'handoff: {os.path.basename(src)} -> RVC {issue_id} ({origin}) [skip ci]'",
        cwd=git_root)
    if rc != 0:
        return (f"Source removed from the index (git rm) but the commit failed: "
                f"{err.strip()} — commit {rel} by hand.")
    return "Source removed and committed on the client side."


def cmd_feedback(vault_path, source, to=None, origin=None, remove=True, skip_ci=True):
    """Ingest an external feedback letter into the RVC vault as a BUG-<n> issue.

    `vault_path` is the *submitting* vault (the CWD the command runs in); the
    letter is moved into the RVC vault resolved via `--to`, `feedback.to=` in
    this vault's `.rvc-root`, or the RVC_FEEDBACK_TO env var.
    """
    src = os.path.abspath(source)
    if not os.path.isfile(src):
        print(f"Error: feedback file not found: {src}")
        sys.exit(1)
    with open(src, "r", errors="replace") as f:
        text = f.read().strip()
    if not text:
        print(f"Error: feedback file is empty: {src}")
        sys.exit(1)

    target = _feedback_target(vault_path, to)
    if not target:
        print("Error: no feedback target vault.")
        print("        Pass --to <vault>, or add `feedback.to=<path>` to this vault's .rvc-root,")
        print("        or set RVC_FEEDBACK_TO.")
        sys.exit(1)
    if not os.path.isdir(target):
        print(f"Error: feedback target is not a directory: {target}")
        sys.exit(1)

    if not origin:
        src_root = find_vault_root(src)
        origin = os.path.basename(src_root) if src_root else "external"

    title = _feedback_title(text) or f"Feedback from {origin}"
    today = datetime.date.today().isoformat()

    try:
        with vault_create_lock(target):
            issue_id = _next_id(target, "BUG")
            filename = f"{issue_id}-{_sanitize_filename(title)}.md"
            directory = resolve_tree(target).get("create") or "00_INBOX"
            filepath = os.path.join(target, directory, filename)
            if os.path.exists(filepath):
                print(f"Error: File already exists: {filepath}")
                sys.exit(1)

            body_lines = text.split("\n")
            # Drop one redundant leading H1 the letter may carry — the canonical
            # `# <ID>: <title>` heading is emitted below (mirrors create --body).
            if body_lines and body_lines[0].lstrip().startswith("# "):
                body_lines = body_lines[1:]
            body = "\n".join(body_lines).strip("\n")

            lines = [
                "---",
                f"id: {issue_id}",
                f"title: {title}",
                "type: bug",
                "priority: P2",
                f"origin: {origin}",
                f"submitted: {today}",
                "---",
                "",
                f"# {issue_id}: {title}",
                "",
            ]
            if body:
                lines.append(body)
            lines.append("")
            with open(filepath, "w") as f:
                f.write("\n".join(lines) + "\n")
    except TimeoutError as e:
        print(f"Error: {e}")
        sys.exit(1)

    sync_after(target, [filepath],
               f"rvc: Ingested {issue_id}: {title} (feedback from {origin})",
               skip_ci=skip_ci)

    removal = ""
    if remove:
        removal = _release_source(src, issue_id, origin)

    pending, done = _bug_counts(target)
    print(f"[RVC] {issue_id} ingested into {os.path.basename(target)} (origin: {origin})")
    if removal:
        print(f"[RVC] {removal}")
    print(f"[RVC] To track it on this vault's plate, add to {os.path.join(vault_path, '.rvc-root')}:")
    print(f"      plate.source.rvc={target}")
    print(f"RVC BUGS — pending: {', '.join(pending) or '—'} | done: {done} of {done + len(pending)}")
    return filepath