#!/usr/bin/env python3
"""BUG-02/03/04 regressions.

- BUG-02: plate AC counters count numbered checkboxes (`1. [ ]`, `2. [x]`),
  not just dash bullets.
- BUG-03: transitions survive apostrophes in filenames (git mv quoting).
- BUG-04: --type drives the minted id prefix, and a rename across prefixes
  never frees a number for reuse (mint floor).
"""

import os

import helpers
from helpers import make_vault, read_frontmatter, rvc_cli, write_issue
from rvc.plate import plate_surface


def _surface(vault, rel_path):
    return plate_surface(os.path.join(vault, rel_path), vault, {})


def test_plate_counts_numbered_boxes():
    """BUG-02: numbered AC lines count as open/done boxes."""
    _, vault = make_vault()
    write_issue(vault, "30_ACTIVE/STORY-090-Numbered.md", {
        "id": "STORY-090", "type": "story", "priority": "P1",
    }, body="## AC\n\n1. [ ] open one\n2. [x] done two\n- [ ] dash open\n- [X] dash done\n")
    row = _surface(vault, "30_ACTIVE/STORY-090-Numbered.md")
    assert (row["open_boxes"], row["done_boxes"]) == (2, 2), row


def test_create_prefix_follows_type():
    """BUG-04 AC1: --type bug/epic mints BUG-/EPIC- unless --prefix pins one."""
    _, vault = make_vault()
    bug = rvc_cli.cmd_create_issue(vault, "A bug", issue_type="bug", priority="P1")
    epic = rvc_cli.cmd_create_issue(vault, "An epic", issue_type="epic", priority="P0")
    story = rvc_cli.cmd_create_issue(vault, "A story", priority="P1")
    assert os.path.basename(bug).startswith("BUG-01-"), bug
    assert read_frontmatter(bug).get("id") == "BUG-01"
    assert os.path.basename(epic).startswith("EPIC-01-"), epic
    assert os.path.basename(story).startswith("STORY-01-"), story


def test_explicit_prefix_still_wins():
    """BUG-04: --prefix overrides the type-derived prefix."""
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(vault, "Pinned", prefix="STORY",
                                    issue_type="bug", priority="P1")
    assert os.path.basename(path).startswith("STORY-01-"), path


def test_mint_floor_survives_rename_across_prefixes():
    """BUG-04 AC2: renaming STORY-040 -> EPIC-004 must not free 040."""
    _, vault = make_vault()
    for n in range(1, 41):
        write_issue(vault, f"20_NEXT/STORY-{n:03d}-F{n}.md",
                    {"id": f"STORY-{n:03d}", "type": "story", "priority": "P1"})
    path = rvc_cli.cmd_create_issue(vault, "Will rename", priority="P1")
    assert os.path.basename(path).startswith("STORY-041-")
    # The birth-rename that started it all:
    os.rename(path, os.path.join(os.path.dirname(path), "EPIC-004-Will-rename.md"))
    # ...and a vault that lost its .rvc-root floor would mint STORY-041 again.
    assert rvc_cli._next_id(vault, "STORY") == "STORY-042"
    again = rvc_cli.cmd_create_issue(vault, "Next one", priority="P1")
    assert os.path.basename(again).startswith("STORY-042-"), again


def test_apostrophe_filename_transitions_cleanly():
    """BUG-03: git mv quoting survives apostrophes in filenames."""
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(vault, "the plate's owed lanes", priority="P1")
    assert "'" in os.path.basename(path), "fixture must contain an apostrophe"
    rvc_cli.cmd_issue_action(vault, "STORY-01", "start")
    moved = os.path.join(vault, "30_ACTIVE", os.path.basename(path))
    assert os.path.exists(moved), f"file did not move: {moved}"
    assert not os.path.exists(path)
