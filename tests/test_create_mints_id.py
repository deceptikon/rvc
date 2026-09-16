#!/usr/bin/env python3
"""STORY-028: `rvc create` mints issues with no `id:` field.

Acceptance criteria under test:
1. `cmd_create` writes `id:` and `title:` into minted frontmatter.
2. ID padding is derived from the vault's existing high-water mark and is
   stable — a vault never produces `STORY-09` next to `STORY-010`.
3. A ticket moved between vaults can be relinked by reading frontmatter alone.
4. Regression: the minted file contains `id:` (the test that would have caught
   the drift).
"""

import os

import helpers
from helpers import make_vault, read_frontmatter, rvc_cli, write_issue


def test_create_mints_id_and_title():
    """AC1 + AC4: minted frontmatter carries id and title."""
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(vault, "Probe", priority="P1")

    fm = read_frontmatter(path)
    assert fm.get("id") == "STORY-01", f"minted frontmatter missing id: {fm}"
    assert fm.get("title") == "Probe", f"minted frontmatter missing title: {fm}"
    assert os.path.basename(path).startswith("STORY-01-")


def test_next_id_padding_matches_high_water_mark_3wide():
    """AC2: a 3-digit vault (STORY-010) mints STORY-011, never STORY-11."""
    _, vault = make_vault()
    for n, slug in ((8, "A"), (9, "B"), (10, "C")):
        write_issue(vault, f"20_NEXT/STORY-{n:03d}-{slug}.md",
                    {"id": f"STORY-{n:03d}", "type": "story", "priority": "P1"})
    assert rvc_cli._next_id(vault, "STORY") == "STORY-011"
    assert rvc_cli._next_id(vault, "STORY") != "STORY-11"


def test_next_id_padding_matches_high_water_mark_2wide():
    """AC2: a 2-digit vault (STORY-19) mints STORY-20, stable padding."""
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-18-X.md",
                {"id": "STORY-18", "type": "story", "priority": "P1"})
    write_issue(vault, "20_NEXT/STORY-19-Y.md",
                {"id": "STORY-19", "type": "story", "priority": "P1"})
    assert rvc_cli._next_id(vault, "STORY") == "STORY-20"


def test_next_id_mixed_padding_takes_widest():
    """AC2: a vault mixing STORY-09 with STORY-010 keeps the widest form."""
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-09-A.md",
                {"id": "STORY-09", "type": "story", "priority": "P2"})
    write_issue(vault, "20_NEXT/STORY-010-B.md",
                {"id": "STORY-010", "type": "story", "priority": "P1"})
    assert rvc_cli._next_id(vault, "STORY") == "STORY-011"


def test_next_id_empty_vault_defaults_to_01():
    """A fresh vault still mints STORY-01 (the historical default)."""
    _, vault = make_vault()
    assert rvc_cli._next_id(vault, "STORY") == "STORY-01"


def test_relink_by_frontmatter_id_after_move():
    """AC3: frontmatter id keys relocation even after the file moves buckets."""
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(vault, "Spike Reranker", priority="P1")
    issue_id = read_frontmatter(path)["id"]

    # Simulate a cross-vault move: same file, different bucket.
    moved = os.path.join(vault, "60_DONE", os.path.basename(path))
    os.rename(path, moved)

    assert read_frontmatter(moved).get("id") == issue_id
    assert rvc_cli.find_file_by_id(vault, issue_id) == moved