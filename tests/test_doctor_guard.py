#!/usr/bin/env python3
"""STORY-029: the vault must not violate its own constitution.

Live files carry a `status:` field (folder = state) and an off-vocabulary
priority (`P0.0.0` sorts nowhere). The structural fix — the point of the story —
is a guard in the tooling, not a one-time sweep: `rvc doctor` refuses `status:`
on a tree that declares a `block` bucket, warns on off-vocabulary priority, and
`--fix` strips/folds them. `rvc create` refuses to mint `status:` on such a
tree, and `rvc rescan` no longer *preserves* the field it is meant to normalize.

Acceptance criteria under test:
1. Every `status:` field stripped from live files (archive may keep what it was
   filed with).
2. Priority vocabulary normalized to P0-P3; `P0.0.0`-style strays fold.
3. `rvc doctor` refuses `status:` on a block-bucket tree and warns on
   off-vocabulary priority; legacy trees are untouched.
4. Mint-time guard: create refuses `status:` on a block-bucket tree.
"""

import datetime as dt

import helpers
from helpers import make_vault, rvc_cli, write_issue


def _newvault_with_drift():
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-101-Sweep.md",
                {"id": "STORY-101", "type": "story", "priority": "P1",
                 "status": "To Do", "created": "2026-09-16"})
    write_issue(vault, "20_NEXT/STORY-102-Stray.md",
                {"id": "STORY-102", "type": "story", "priority": "P0.0.0",
                 "created": "2026-09-16"})
    write_issue(vault, "20_NEXT/STORY-103-LegacyWord.md",
                {"id": "STORY-103", "type": "story", "priority": "High",
                 "created": "2026-09-16"})
    return vault


def test_doctor_refuses_status_on_newvault():
    """AC3: a status: field in a live bucket is a refusal-grade violation."""
    vault = _newvault_with_drift()
    report = rvc_cli.cmd_doctor(vault)
    assert len(report["violations"]) == 1, report
    assert "STORY-101" in report["violations"][0]
    assert len(report["warnings"]) == 2, report  # P0.0.0 + High


def test_doctor_passes_clean_newvault():
    """AC3: a clean block-tree vault audits clean."""
    vault = make_vault()[1]
    write_issue(vault, "20_NEXT/STORY-200-Clean.md",
                {"id": "STORY-200", "type": "story", "priority": "P1"})
    report = rvc_cli.cmd_doctor(vault)
    assert report["violations"] == [] and report["warnings"] == []


def test_doctor_ignores_archive():
    """AC1: archive keeps what it was filed with — not a violation."""
    _, vault = make_vault()
    write_issue(vault, "90_ARCHIVE/done/STORY-900-Archived.md",
                {"id": "STORY-900", "type": "story", "priority": "P3",
                 "status": "Done"})
    report = rvc_cli.cmd_doctor(vault)
    assert report["violations"] == [], report


def test_doctor_legacy_tree_untouched():
    """AC3: legacy trees (no block bucket) keep status/legacy priority."""
    _, vault = make_vault()
    # rewrite .rvc-root to a legacy-shape tree (no block)
    import os
    with open(os.path.join(vault, ".rvc-root"), "w") as f:
        f.write("vault=legacy\n")
        for verb, d in helpers.NEWVAULT_TREE.items():
            if verb == "block":
                continue
            f.write(f"tree.{verb}={d}\n")
    write_issue(vault, "20_NEXT/STORY-300-Legacy.md",
                {"id": "STORY-300", "type": "story", "priority": "High",
                 "status": "To Do"})
    report = rvc_cli.cmd_doctor(vault)
    assert report["violations"] == [] and report["warnings"] == [], report


def test_doctor_fix_strips_and_folds():
    """AC3 + AC1/AC2: --fix removes status:, folds P0.0.0 -> P0 and High -> P1."""
    vault = _newvault_with_drift()
    report = rvc_cli.cmd_doctor(vault, fix=True)
    assert len(report["fixed"]) == 3, report

    recheck = rvc_cli.cmd_doctor(vault)
    assert recheck["violations"] == [] and recheck["warnings"] == [], recheck

    import os
    fm = helpers.read_frontmatter(os.path.join(vault, "20_NEXT/STORY-101-Sweep.md"))
    assert "status" not in fm, fm
    fm2 = helpers.read_frontmatter(os.path.join(vault, "20_NEXT/STORY-102-Stray.md"))
    assert fm2.get("priority") == "P0", fm2
    fm3 = helpers.read_frontmatter(os.path.join(vault, "20_NEXT/STORY-103-LegacyWord.md"))
    assert fm3.get("priority") == "P1", fm3


def test_create_refuses_status_on_newvault():
    """AC4: mint-time guard — create refuses status: on a block-bucket tree."""
    _, vault = make_vault()
    try:
        rvc_cli.cmd_create_issue(vault, "Probe", priority="P1",
                                 extra_frontmatter={"status": "To Do"})
    except SystemExit as e:
        assert e.code == 1
    else:
        raise AssertionError("expected SystemExit refusing status: on a block tree")


def test_rescan_normalizer_folds_and_strips():
    """AC3: rescan's normalizer strips status: and folds stray priority."""
    _, vault = make_vault()
    fm = {
        "id": "STORY-777", "type": "story", "priority": "P0.0.0",
        "status": "To Do", "title": "Stray",
    }
    out, changed = helpers.vault_restructure.normalize_frontmatter(
        dict(fm), "20_NEXT/STORY-777-Stray.md", "STORY-777-Stray.md", vault)
    assert changed is True
    assert "status" not in out, out
    assert out.get("priority") == "P0", out


def test_create_mints_no_status_by_default():
    """AC4: plain create on a block tree mints without status:."""
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(vault, "Clean Mint", priority="P1")
    fm = helpers.read_frontmatter(path)
    assert "status" not in fm, fm
    assert fm.get("priority") == "P1"