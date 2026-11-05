#!/usr/bin/env python3
"""BUG-05/06/07/08 regressions — FEEDBACK-rvc round 2 (2026-11-05, ADLAI).

- BUG-05: `_next_id` scans the WHOLE vault, so an id resting where the tree
  never looks (`90_ARCHIVE/FROM INBOX/`, not a bucket of any tree verb) can
  no longer be minted twice. Ids are permanent.
- BUG-06: every parked file renders on the plate — the measured blind spot
  was a non-issue ESSAY in `50_DEFERRED/` visible on no lane — and waiting
  rows carry a bucket tag so 40_DECIDE rulings read apart from 50_DEFERRED
  parks under a lane title that names both.
- BUG-07: search falls back to all-terms matching when the whole phrase hits
  nothing ("filename" must still match "filenames"), and an empty result
  says why instead of a bare "No results".
- BUG-08: the flag that runs CI is `--no-skip-ci` (alias `--ci`); `--skip-ci`
  survives only as a deprecated, warning alias of the flag it used to betray.
"""

import contextlib
import io
import os

import helpers
from helpers import capture_stdout, make_vault, plate_json, rvc_cli, write_issue


# ── BUG-05: mint never collides with off-tree ids ────────────────────────────

def test_mint_skips_id_resting_off_tree():
    """STORY-153 in an archive subfolder the tree never names is not re-minted."""
    _, vault = make_vault()
    write_issue(vault, "90_ARCHIVE/FROM INBOX/STORY-153-Old.md",
                {"id": "STORY-153", "type": "story", "priority": "P2"})
    assert rvc_cli._next_id(vault, "STORY") == "STORY-154"
    path = rvc_cli.cmd_create_issue(vault, "Fresh", priority="P1")
    assert os.path.basename(path).startswith("STORY-154-"), path
    # and only one STORY-153 exists anywhere in the vault
    hits = []
    for root, _, files in os.walk(vault):
        hits += [os.path.join(root, f) for f in files if f.startswith("STORY-153")]
    assert len(hits) == 1, hits


# ── BUG-06: parked files render, bucket tags tell rulings from parks ─────────

def test_parked_non_issue_renders_with_bucket_tag():
    """The measured ESSAY blind spot: parked non-issues must be on a lane."""
    _, vault = make_vault()
    write_issue(vault, "50_DEFERRED/ESSAY--The-Pilot-and-the-Prison-Guard.md",
                {"type": "essay", "priority": "P3", "created": "2026-11-05"},
                body="Parked on purpose.\n")
    write_issue(vault, "40_DECIDE/STORY-157-Blocked.md",
                {"id": "STORY-157", "type": "story", "priority": "P1",
                 "created": "2026-11-05"},
                body="## @Q@2026-11-05\nWaiting on a ruling.\n")

    payload = plate_json(vault)
    waiting = {row["path"] for row in payload["lanes"]["waiting"]}
    assert "50_DEFERRED/ESSAY--The-Pilot-and-the-Prison-Guard.md" in waiting, waiting
    assert "40_DECIDE/STORY-157-Blocked.md" in waiting, waiting
    # A park and a ruling are waiting, never late
    overdue = {row["path"] for row in payload["lanes"]["overdue"]}
    assert not (waiting & overdue), overdue

    _, out = capture_stdout(rvc_cli.cmd_plate, vault, fmt="text")
    assert "[50_DEFERRED] ESSAY--The-Pilot-and-the-Prison-Guard.md" in out, out
    assert "[40_DECIDE] STORY-157-Blocked.md" in out, out
    # The lane title names both kinds of not-late; no more "deferred on purpose".
    assert "on a ruling (40_DECIDE) or parked on purpose (50_DEFERRED)" in out
    assert "deferred on purpose (not late)" not in out


# ── BUG-07: search all-terms fallback + explained empty results ──────────────

def test_search_all_terms_fallback_matches_plural():
    """`search "apostrophe filename"` must hit a file that says "filenames"."""
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-142-Apostrophe.md",
                {"id": "STORY-142", "type": "story", "priority": "P1"},
                body="fails its atomic git mv on filenames containing an apostrophe\n")

    _, whole = capture_stdout(rvc_cli.cmd_search, vault, "apostrophe filename")
    assert "all-terms fallback" in whole, whole
    assert "filenames containing an apostrophe" in whole, whole

    _, one = capture_stdout(rvc_cli.cmd_search, vault, "apostrophe")
    assert "1 matches" in one and "all-terms fallback" not in one, one


def test_search_no_results_says_why():
    _, vault = make_vault()
    _, multi = capture_stdout(rvc_cli.cmd_search, vault, "zzznothing qqqmissing")
    assert "No results for 'zzznothing qqqmissing'" in multi
    assert "zzznothing, qqqmissing" in multi, multi
    assert "Try fewer words" in multi

    _, single = capture_stdout(rvc_cli.cmd_search, vault, "zzznothing")
    assert "No results for 'zzznothing'" in single
    assert "Try a shorter fragment" in single


# ── BUG-08: --no-skip-ci is the CI flag; --skip-ci is a warned alias ─────────

def test_ci_flag_naming():
    default = rvc_cli.build_parser().parse_args(["issue", "STORY-1", "done"])
    assert default.skip_ci is True, "[skip ci] must be the default stamp"

    for argv, flag in (
        (["issue", "STORY-1", "done", "--no-skip-ci"], "--no-skip-ci"),
        (["create", "T", "--ci"], "--ci"),
        (["feedback", "F.md", "--no-skip-ci"], "--no-skip-ci"),
    ):
        assert rvc_cli.build_parser().parse_args(argv).skip_ci is False, flag


def test_skip_ci_alias_warns_and_still_works():
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        args = rvc_cli.build_parser().parse_args(["create", "T", "--skip-ci"])
    assert args.skip_ci is False
    assert "deprecated" in buf.getvalue() and "--no-skip-ci" in buf.getvalue()


def test_help_leads_with_the_inversion():
    _, create_help = capture_stdout(rvc_cli.cmd_help, "create")
    assert "--no-skip-ci" in create_help
    assert "default ON" in create_help
    assert "--skip-ci    disable" not in create_help
