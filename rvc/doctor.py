"""Vault constitution audit and automated repair."""

import os
import sys
import re

from rvc.core import (
    resolve_tree, tree_dirs, hot_dirs, LEGACY_PRIORITY_TO_P,
    _parse_domain_from_filename, frontmatter_domain_tags,
)
from rvc.plate import plate_frontmatter

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
    unslugged = []  # files whose domain lives only in frontmatter — one line, not N
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

                # Domain checks: the filename slug and the frontmatter field are
                # one fact in two places, so drift is a per-file warning. A file
                # that simply has no slug yet is the pre-migration state of the
                # whole tree (19 of them here) — counted, named once, not spammed.
                file_domain = _parse_domain_from_filename(fn)
                fm_tags = frontmatter_domain_tags(text)
                if file_domain and fm_tags and file_domain not in fm_tags:
                    report["warnings"].append(
                        f"{rel}: domain mismatch — filename '{file_domain}' not in "
                        f"frontmatter [{', '.join(fm_tags)}]")
                elif file_domain and not fm_tags:
                    report["warnings"].append(
                        f"{rel}: filename has domain '{file_domain}' but no domain_tags in frontmatter")
                elif fm_tags and not file_domain:
                    unslugged.append(rel)

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

    if unslugged:
        noun = "file" if len(unslugged) == 1 else f"{len(unslugged)} files"
        verb = "has" if len(unslugged) == 1 else "have"
        shown = ", ".join(unslugged[:3])
        rest = f" … (+{len(unslugged) - 3} more)" if len(unslugged) > 3 else ""
        report["warnings"].append(
            f"{noun} {verb} domain_tags but no slug in filename: {shown}{rest}"
            " — rvc set ⟨ID⟩ --domain ⟨slug⟩ stamps the primary one")
    return report

