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
    find_git_root, find_vault_root, find_marker_dir, marker_file, _ref_vault_dir,
    resolve_tree, _next_id, vault_create_lock, run_cmd,
)
from rvc.git import sync_after, is_tracked
from rvc.issues import _sanitize_filename

_BUG_ID_RE = re.compile(r"^(BUG-\d+)")


def _default_feedback_target(cli_root=None):
    """Auto-discover the RVC vault next to the installed CLI.

    `rvc` on PATH is a symlink/launcher into RVC's own `rvc-cli.py`; the RVC
    vault lives at its sibling `rvc-vault/`. The tool knows its own home, so a
    client never has to point at it. `cli_root` is a test hook.
    """
    if cli_root is None:
        argv0 = sys.argv[0] if sys.argv and sys.argv[0] else None
        if not argv0:
            return None
        cli_root = os.path.dirname(os.path.realpath(argv0))
    if not cli_root:
        return None
    candidate = os.path.join(cli_root, "rvc-vault")
    if os.path.isdir(candidate) and os.path.exists(os.path.join(candidate, ".rvc-root")):
        return os.path.abspath(candidate)
    return None


def _feedback_target(vault_path, explicit, cli_root=None):
    """Resolve the feedback target: `--to` > `feedback.to=` in .rvc-root >
    RVC_FEEDBACK_TO env > auto-discovery (the RVC vault next to the CLI).

    The persisted `.rvc-root` line is the tool's own auto-written memory of the
    first `--to`, so subsequent runs need no flag at all.
    """
    if explicit:
        return os.path.abspath(explicit)
    root_file = marker_file(vault_path) or os.path.join(vault_path, ".rvc-root")
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
    return _default_feedback_target(cli_root)


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


def _ensure_feedback_config(client_vault, target, name="rvc", alias="F"):
    """Auto-configure the client's `.rvc-root` feedback lane.

    Writes `feedback.to=`, `plate.source.<name>=`, `plate.alias.<name>=` only
    when missing (idempotent; a user's own values win). Returns the lines added
    so the caller can report them. Never configures a vault against itself.
    """
    if os.path.abspath(client_vault) == os.path.abspath(target):
        return []
    marker_dir = find_marker_dir(client_vault) or client_vault
    root_file = os.path.join(marker_dir, ".rvc-root")
    present = set()
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("feedback.to="):
                    present.add("feedback.to")
                elif line.startswith(f"plate.source.{name}="):
                    present.add("plate.source")
                elif line.startswith(f"plate.alias.{name}="):
                    present.add("plate.alias")
    want = [
        ("feedback.to", f"feedback.to={target}"),
        ("plate.source", f"plate.source.{name}={target}"),
        ("plate.alias", f"plate.alias.{name}={alias}"),
    ]
    added = [text for key, text in want if key not in present]
    if not added:
        return []
    content = ""
    if os.path.exists(root_file):
        with open(root_file, "r", errors="replace") as f:
            content = f.read()
    if content and not content.endswith("\n"):
        content += "\n"
    with open(root_file, "w") as f:
        f.write(content + "\n".join(added) + "\n")
    return added


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
    # `git rm` (git 2.55+) prunes now-empty parent directories from the working
    # tree; the client's bucket (00_INBOX etc.) is vault structure and must
    # survive the handoff, so recreate it when git swept it away.
    parent = os.path.dirname(src)
    if not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    rc, _, err = run_cmd(
        f"git commit -qm 'handoff: {os.path.basename(src)} -> RVC {issue_id} ({origin}) [skip ci]'",
        cwd=git_root)
    if rc != 0:
        return (f"Source removed from the index (git rm) but the commit failed: "
                f"{err.strip()} — commit {rel} by hand.")
    return "Source removed and committed on the client side."


def cmd_feedback(vault_path, source, to=None, origin=None, remove=True, skip_ci=True, cli_root=None):
    """Ingest an external feedback letter into the RVC vault as a BUG-<n> issue.

    `vault_path` is the *submitting* vault (the CWD the command runs in); the
    target is resolved via `--to`, the client's own `.rvc-root` (auto-written on
    first use), RVC_FEEDBACK_TO, or auto-discovery of the vault next to the CLI.
    The client's `.rvc-root` feedback lane is auto-configured on first use, so
    no manual setup is ever needed on the client side.
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

    target = _feedback_target(vault_path, to, cli_root=cli_root)
    if not target:
        print("Error: no feedback target vault.")
        print("        Pass --to <vault>, add `feedback.to=<path>` to this vault's .rvc-root,")
        print("        set RVC_FEEDBACK_TO, or run from a vault near an installed RVC CLI.")
        sys.exit(1)
    if not os.path.isdir(target):
        print(f"Error: feedback target is not a directory: {target}")
        sys.exit(1)
    # STORY-037: the target may be a project root whose vault lives in a named
    # subdirectory (`vault=<name>` in the project-root marker); descend into the
    # real vault so ingest lands in its buckets. Bare targets with no marker
    # stay as given (a later open() surfaces the missing-directory error).
    target = _ref_vault_dir(os.path.abspath(target))

    if not origin:
        src_root = find_vault_root(os.path.dirname(src))
        if src_root:
            # new-layout vaults live in a named subdir; label the submitter with
            # the PROJECT (marker-root) name, not the generic bucket dir name.
            marker_dir = find_marker_dir(src_root) or src_root
            origin = os.path.basename(marker_dir)
        else:
            origin = "external"

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

    configured = _ensure_feedback_config(vault_path, target)

    pending, done = _bug_counts(target)
    print(f"[RVC] {issue_id} ingested into {os.path.basename(target)} (origin: {origin})")
    if removal:
        print(f"[RVC] {removal}")
    if os.path.abspath(vault_path) != os.path.abspath(target):
        cfg_root = os.path.join(find_marker_dir(vault_path) or vault_path, ".rvc-root")
        if configured:
            print(f"[RVC] Auto-configured this vault's plate in {cfg_root}:")
            for text in configured:
                print(f"      {text}")
        else:
            print(f"[RVC] Feedback lane already configured ({cfg_root}).")
    print(f"RVC BUGS — pending: {', '.join(pending) or '—'} | done: {done} of {done + len(pending)}")
    return filepath