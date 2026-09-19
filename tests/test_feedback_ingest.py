#!/usr/bin/env python3
"""`rvc feedback @<file>`: external feedback becomes a BUG-<n> in the RVC vault.

The letter travels: content lands in the target vault (type: bug, origin:
<client>), the source is removed, and the command prints the submitter's
dashboard line. BUG- is not a parallel type — `bug` already flows through
triage and plate with zero registration (STORY-036).
"""

import os

import helpers
from helpers import make_vault, read_frontmatter, rvc_cli, write_issue

LETTER_TEXT = (
    "# FEEDBACK-rvc\n\n"
    "- **2026-09-19:** transitions on untracked issues still confuse new users.\n"
)


def _write_letter(vault, rel="00_INBOX/FEEDBACK-rvc.md", text=LETTER_TEXT):
    path = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path


def test_feedback_ingests_letter_as_bug():
    """AC1: the letter lands in the target vault as BUG-01, source removed."""
    _, client = make_vault()
    _, target = make_vault()
    letter = _write_letter(client)

    ret, out = helpers.capture_stdout(
        rvc_cli.cmd_feedback, client, letter, to=target, origin="adlai")

    created = os.path.join(target, "00_INBOX", "BUG-01-FEEDBACK-rvc.md")
    assert ret == created, f"must return the created path, got {ret}"
    assert os.path.exists(created)
    fm = read_frontmatter(created)
    assert fm["id"] == "BUG-01"
    assert fm["type"] == "bug"
    assert fm["origin"] == "adlai"
    content = open(created).read()
    assert "transitions on untracked issues" in content, "letter body must survive"
    assert content.startswith("---"), "minted file must start with frontmatter"
    assert "\n# BUG-01: FEEDBACK-rvc\n" in content, \
        "canonical H1 must be present once; the letter's own heading must be dropped"
    assert not os.path.exists(letter), "source letter must be moved out"
    assert "RVC BUGS" in out, f"dashboard line missing:\n{out}"
    assert "pending: BUG-01" in out


def test_feedback_mints_sequential_padded_ids():
    """AC2: high-water-mark padding — BUG-07 on disk mints BUG-08, never BUG-8."""
    _, client = make_vault()
    _, target = make_vault()
    write_issue(target, "20_NEXT/BUG-07-Old.md", {"id": "BUG-07", "type": "bug", "priority": "P2"})
    letter = _write_letter(client)

    rvc_cli.cmd_feedback(client, letter, to=target, origin="adlai", remove=False)

    assert os.path.exists(os.path.join(target, "00_INBOX", "BUG-08-FEEDBACK-rvc.md"))
    assert os.path.exists(letter), "--no-remove must keep the source letter"


def test_feedback_to_from_rvc_root_config():
    """AC3: `feedback.to=` in the client's .rvc-root replaces `--to`."""
    _, client = make_vault()
    _, target = make_vault()
    with open(os.path.join(client, ".rvc-root"), "a") as f:
        f.write(f"feedback.to={target}\n")
    letter = _write_letter(client)

    rvc_cli.cmd_feedback(client, letter, origin="adlai")

    assert os.path.exists(os.path.join(target, "00_INBOX", "BUG-01-FEEDBACK-rvc.md"))


def test_feedback_errors_on_missing_file():
    """A missing letter must exit non-zero, never mint anything."""
    _, client = make_vault()
    _, target = make_vault()
    try:
        rvc_cli.cmd_feedback(client, "/nonexistent/letter.md", to=target, origin="x")
        assert False, "missing file must exit"
    except SystemExit as e:
        assert e.code == 1