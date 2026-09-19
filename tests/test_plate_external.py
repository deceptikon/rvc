#!/usr/bin/env python3
"""Plate external-source lane: a client vault renders another vault's bugs.

`plate.source.<name>=<vault>` + `plate.alias.<name>=F` in the client's
.rvc-root yield a `rvc: pending: F-01 | done: 1 of 2` lane — IDs and counts
only, zero content crosses the boundary. The F-alias is "rendering, not a
record" (STORY-039 PoC).
"""

import os

import helpers
from helpers import make_vault, rvc_cli, write_issue


def _client_with_source(client, target, name="rvc", alias="F"):
    with open(os.path.join(client, ".rvc-root"), "a") as f:
        f.write(f"plate.source.{name}={target}\n")
        f.write(f"plate.alias.{name}={alias}\n")


def _seed_bugs(target):
    write_issue(target, "20_NEXT/BUG-01-Crash.md",
                {"id": "BUG-01", "type": "bug", "priority": "P2"})
    write_issue(target, "60_DONE/BUG-02-Fixed.md",
                {"id": "BUG-02", "type": "bug", "priority": "P1"})


def test_external_lane_text_shows_alias_and_counts():
    """A pending + a done bug render as `pending: F-01 | done: 1 of 2`."""
    _, client = make_vault()
    _, target = make_vault()
    _client_with_source(client, target)
    _seed_bugs(target)

    out = helpers.capture_stdout(rvc_cli.cmd_plate, client, fmt="text")[1]

    assert "EXTERNAL FEEDBACK" in out
    assert "pending: F-01" in out, f"aliased pending id missing:\n{out}"
    assert "done: 1 of 2" in out, f"done count missing:\n{out}"
    assert "BUG-01" not in out, "raw bug ids must not leak when aliased"


def test_external_lane_json():
    """JSON payload carries structured external state."""
    _, client = make_vault()
    _, target = make_vault()
    _client_with_source(client, target)
    _seed_bugs(target)

    payload = helpers.plate_json(client)
    ext = payload["external"]["rvc"]
    assert ext["pending"] == ["F-01"]
    assert ext["done"] == 1
    assert ext["total"] == 2


def test_no_sources_no_external_lane():
    """A vault without plate.source.* is unaffected — no behavioural change."""
    _, client = make_vault()
    out = helpers.capture_stdout(rvc_cli.cmd_plate, client, fmt="text")[1]
    assert "EXTERNAL FEEDBACK" not in out