#!/usr/bin/env python3
"""STORY-034 AC1 + AC4: handle resolution and triage type gating.

AC1: `rvc issue <ID> <verb>` must exit non-zero with "no issue matches <handle>"
     when the handle resolves to no file — before any transition line.
AC4: `rvc issue <ID> triage` must warn on stderr and refuse to move a file whose
     frontmatter `type:` has no bucket mapping (e.g. `proposal`), telling the
     operator to place it by hand.
"""

import contextlib
import io
import os
import sys

import helpers
from helpers import make_vault, rvc_cli, write_issue


def run_action(vault, issue_id, action):
    """Call cmd_issue_action capturing stdout+stderr; returns (rc, out, err).

    `cmd_issue_action` exits via SystemExit on failure — the CLI contract.
    """
    out_buf, err_buf = io.StringIO(), io.StringIO()
    rc = 0
    try:
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            rvc_cli.cmd_issue_action(vault, issue_id, action)
    except SystemExit as e:
        rc = e.code if isinstance(e.code, int) else 1
    return rc, out_buf.getvalue(), err_buf.getvalue()


def test_unresolvable_handle_exits_nonzero_no_transition():
    """AC1: a handle matching no file fails before any success line."""
    _, vault = make_vault()
    rc, out, err = run_action(vault, "STORY-999", "supersede")

    assert rc != 0, "unresolvable handle must exit non-zero"
    assert "no issue matches STORY-999" in err, f"expected stderr message, got: {err!r}"
    assert "moved" not in out, f"no transition line may print, got: {out!r}"
    assert "Committing" not in out, f"no commit line may print, got: {out!r}"


def test_unresolvable_handle_with_invalid_action():
    """Regression: a bad verb still reports the verb error, not a false green."""
    _, vault = make_vault()
    rc, out, err = run_action(vault, "STORY-999", "bogus-verb")

    assert rc != 0
    assert "invalid action" in out, f"expected action error, got: {out!r}"


def test_triage_refuses_proposal_type():
    """AC4: a `type: proposal` deposit is not triaged into the queue."""
    _, vault = make_vault()
    prop = write_issue(vault, "00_INBOX/PROPOSAL--Something.md",
                       {"type": "proposal", "title": "Something"})

    rc, out, err = run_action(vault, "PROPOSAL", "triage")

    assert rc != 0, "proposal triage must exit non-zero"
    assert "no triage target" in err, f"expected stderr warning, got: {err!r}"
    assert os.path.exists(prop), "the proposal must not be moved"
    assert os.path.dirname(prop).endswith("00_INBOX"), "proposal must stay put"


def test_triage_refuses_feedback_type():
    """AC4: feedback (another non-issue type) is likewise not auto-triaged."""
    _, vault = make_vault()
    fb = write_issue(vault, "00_INBOX/FEEDBACK-x.md",
                     {"type": "feedback", "title": "x"})

    rc, _, err = run_action(vault, "FEEDBACK-x", "triage")

    assert rc != 0
    assert "no triage target" in err
    assert os.path.exists(fb)


def test_triage_moves_story_normally():
    """AC4 sanity: a proper issue file still triages into 20_NEXT."""
    _, vault = make_vault()
    path = write_issue(vault, "00_INBOX/STORY-05-Foo.md",
                       {"id": "STORY-05", "type": "story", "priority": "P1"},
                       body="## Context\n\n## Acceptance Criteria\n- [ ] x")

    rc, out, err = run_action(vault, "STORY-05", "triage")

    assert rc == 0, f"story triage must succeed, stderr: {err!r}"
    assert "no triage target" not in err
    assert not os.path.exists(path), "source file must be gone"
    moved = os.path.join(vault, "20_NEXT", "STORY-05-Foo.md")
    assert os.path.exists(moved), f"expected the story in 20_NEXT, got: {out!r}"


def test_other_verbs_still_route_non_issue_files():
    """AC4 scope: gating applies to triage only — supersede still moves a proposal."""
    _, vault = make_vault()
    prop = write_issue(vault, "00_INBOX/PROPOSAL--Something.md",
                       {"type": "proposal", "title": "Something"})

    rc, _, err = run_action(vault, "PROPOSAL", "supersede")

    assert rc == 0, f"supersede must still work for proposals, stderr: {err!r}"
    assert not os.path.exists(prop)
    assert os.path.exists(os.path.join(
        vault, "90_ARCHIVE", "superseded", "PROPOSAL--Something.md"))