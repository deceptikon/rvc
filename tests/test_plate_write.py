#!/usr/bin/env python3
"""STORY-034 AC3: `rvc plate --write` persists the rendering to PLATE.md.

The constitution calls PLATE.md "a rendering, not a record" — it must be
rebuildable from the tree alone. `--write` writes the exact text that would be
printed to stdout, so the file cannot silently rot.
"""

import os

import helpers
from helpers import make_vault, plate_json, rvc_cli, write_issue


def test_plate_write_persists_rendering():
    """AC3: --write writes 10_CONTEXT/PLATE.md identical to stdout."""
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-03-X.md",
                {"id": "STORY-03", "type": "story", "priority": "P1"})

    out, stdout = helpers.capture_stdout(rvc_cli.cmd_plate, vault, write=True)
    assert out is None
    plate_path = os.path.join(vault, "10_CONTEXT", "PLATE.md")
    assert os.path.exists(plate_path), "PLATE.md must be written"
    with open(plate_path) as f:
        body = f.read()
    # The file embeds the exact stdout rendering; the [RVC] confirmation line
    # is tool status that follows it.
    assert body == stdout[:len(body)], (
        "written PLATE.md must start with the exact stdout rendering")
    assert f"[RVC] Wrote plate rendering: {plate_path}" in stdout
    assert body.startswith(f"PLATE — {os.path.basename(vault)}")
    assert "STORY-03-X.md" in body


def test_plate_without_write_does_not_touch_tree():
    """AC3: plain `rvc plate` keeps stdout-only behavior — no PLATE.md appears."""
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-03-X.md",
                {"id": "STORY-03", "type": "story", "priority": "P1"})

    _, stdout = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    assert not os.path.exists(os.path.join(vault, "10_CONTEXT", "PLATE.md")), (
        "without --write nothing may be written")
    assert "PLATE —" in stdout


def test_plate_write_json_is_ignored():
    """AC3 scope: --write applies to the text rendering; JSON is not persisted."""
    _, vault = make_vault()
    payload = plate_json(vault)
    assert "lanes" in payload

    props = plate_json(vault, write=True)
    assert "lanes" in props
    assert not os.path.exists(os.path.join(vault, "10_CONTEXT", "PLATE.md")), (
        "--write with --format json must not write a PLATE.md")