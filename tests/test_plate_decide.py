#!/usr/bin/env python3
"""STORY-031: `rvc plate` renders no `40_DECIDE` root stories.

A blocked-decision *story* (type: story) whose file sits in `40_DECIDE/` root is
invisible to `rvc plate`: the waiting lane only rendered non-issue files from
that bucket, so a P1 item awaiting a ruling looked like it did not exist.

Acceptance criteria under test:
1. A story (`type: story`) in `40_DECIDE/` root appears in `rvc plate` text and
   JSON output (in the waiting lane, mirroring the human DQL "Awaiting a
   ruling" lane which lists all of `40_DECIDE`).
2. Existing behavior unchanged: proposals in `40_DECIDE` and deferred issues
   still render as today.
3. A fresh blocked-decision story is *not* mislabeled as overdue.
"""

import datetime as dt

from helpers import capture_stdout, make_vault, plate_json, rvc_cli, write_issue

TODAY = dt.date(2026, 9, 16)


def _decide_story(vault, name="STORY-113-Regulatory-data-boundaries.md"):
    return write_issue(
        vault,
        f"40_DECIDE/{name}",
        {"id": "STORY-113", "type": "story", "priority": "P1", "created": "2026-09-16"},
        body="## @Q@2026-09-16\nWaiting on a ruling.\n",
    )


def test_decide_story_appears_in_json():
    """AC1 (JSON): a blocked-decision story lands in the waiting lane."""
    _, vault = make_vault()
    _decide_story(vault)

    payload = plate_json(vault, today=TODAY)
    waiting = payload["lanes"]["waiting"]
    names = [row["name"] for row in waiting]
    assert "STORY-113-Regulatory-data-boundaries.md" in names, (
        f"blocked-decision story missing from waiting lane; lanes={ {k: [r['name'] for r in v] for k, v in payload['lanes'].items()} }"
    )


def test_decide_story_appears_in_text():
    """AC1 (text): the same story shows in the text render."""
    _, vault = make_vault()
    _decide_story(vault)

    _, out = capture_stdout(rvc_cli.cmd_plate, vault, fmt="text", today=TODAY)
    assert "STORY-113-Regulatory-data-boundaries.md" in out


def test_decide_story_not_overdue_when_fresh():
    """AC3: a blocked story awaiting a ruling is waiting, not late."""
    _, vault = make_vault()
    _decide_story(vault)

    payload = plate_json(vault, today=TODAY)
    overdue = [row["name"] for row in payload["lanes"]["overdue"]]
    assert "STORY-113-Regulatory-data-boundaries.md" not in overdue


def test_decide_proposal_still_waits():
    """AC2: a non-issue proposal in 40_DECIDE keeps rendering (unchanged)."""
    _, vault = make_vault()
    write_issue(
        vault,
        "40_DECIDE/PROPOSAL--Cross-Dev-Review.md",
        {"type": "proposal", "priority": "P2", "created": "2026-09-16"},
        body="## @Q@2026-09-16\nProposed process change.\n",
    )

    payload = plate_json(vault, today=TODAY)
    names = [row["name"] for row in payload["lanes"]["waiting"]]
    assert "PROPOSAL--Cross-Dev-Review.md" in names


def test_deferred_issue_still_waits():
    """AC2: a deferred issue keeps rendering in waiting (unchanged)."""
    _, vault = make_vault()
    write_issue(
        vault,
        "50_DEFERRED/STORY-099-Parked.md",
        {"id": "STORY-099", "type": "story", "priority": "P3", "created": "2026-08-01"},
        body="## @Q@2026-08-01\nParked on purpose.\n",
    )

    payload = plate_json(vault, today=TODAY)
    names = [row["name"] for row in payload["lanes"]["waiting"]]
    assert "STORY-099-Parked.md" in names