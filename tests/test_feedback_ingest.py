#!/usr/bin/env python3
"""`rvc feedback @<file>`: external feedback becomes a BUG-<n> in the RVC vault.

The letter travels: content lands in the target vault (type: bug, origin:
<client>), the source is removed, and the command prints the submitter's
dashboard line. BUG- is not a parallel type — `bug` already flows through
triage and plate with zero registration (STORY-036).

Client setup is automatic: the target vault resolves from `--to`, the client's
own `.rvc-root` (auto-written on first use), the environment, or auto-discovery
of the vault next to the installed CLI — and the client's `.rvc-root` feedback
lane is written for it on first use, no hand-editing.
"""

import os
import tempfile

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


# --- auto-setup: no client hand-editing of .rvc-root -------------------------


def _make_vault_at(path):
    """Build a newvault tree at an arbitrary path (for the CLI-adjacent root)."""
    os.makedirs(path)
    with open(os.path.join(path, ".rvc-root"), "w") as f:
        f.write("vault=scratch\n")
        for verb, directory in sorted(helpers.NEWVAULT_TREE.items()):
            f.write(f"tree.{verb}={directory}\n")
    for directory in set(helpers.NEWVAULT_TREE.values()):
        os.makedirs(os.path.join(path, directory), exist_ok=True)
    return path


def _config_lines(vault):
    with open(os.path.join(vault, ".rvc-root")) as f:
        return f.read().splitlines()


def test_feedback_auto_writes_client_config():
    """AC: first use self-writes feedback.to / plate.source.rvc / plate.alias.rvc."""
    _, client = make_vault()
    _, target = make_vault()
    letter = _write_letter(client)

    _, out = helpers.capture_stdout(
        rvc_cli.cmd_feedback, client, letter, to=target, origin="adlai")

    lines = _config_lines(client)
    assert f"feedback.to={target}" in lines
    assert f"plate.source.rvc={target}" in lines
    assert "plate.alias.rvc=F" in lines
    assert "Auto-configured this vault's plate" in out
    assert "plate.source.rvc" in out, "the written lines must be shown"


def test_feedback_config_is_idempotent():
    """AC: a second run adds nothing and reports the lane already configured."""
    _, client = make_vault()
    _, target = make_vault()
    letter1 = _write_letter(client, "00_INBOX/FEEDBACK-rvc.md")
    rvc_cli.cmd_feedback(client, letter1, to=target, origin="adlai")
    before = _config_lines(client)

    letter2 = _write_letter(client, "00_INBOX/FEEDBACK-rvc-2.md")
    _, out = helpers.capture_stdout(
        rvc_cli.cmd_feedback, client, letter2, to=target, origin="adlai")

    after = _config_lines(client)
    assert after == before, "no duplicate config lines on second use"
    assert "already configured" in out


def test_feedback_auto_discovers_cli_adjacent_vault():
    """AC: with no --to and no config, the vault next to the CLI is the target."""
    root = tempfile.mkdtemp(prefix="rvc-fb-disc-")
    target = _make_vault_at(os.path.join(root, "rvc-vault"))
    _, client = make_vault()
    letter = _write_letter(client)

    rvc_cli.cmd_feedback(client, letter, origin="adlai", cli_root=root)

    created = os.path.join(target, "00_INBOX", "BUG-01-FEEDBACK-rvc.md")
    assert os.path.exists(created), f"auto-discovered target not used: {target}"
    assert not os.path.exists(letter), "source letter must still travel"


def test_feedback_self_ingest_does_not_self_configure():
    """Ingesting into your own vault must not write a feedback lane for itself."""
    root = tempfile.mkdtemp(prefix="rvc-fb-self-")
    target = _make_vault_at(os.path.join(root, "rvc-vault"))
    letter = _write_letter(target, "00_INBOX/SELF-FEEDBACK.md")
    before = _config_lines(target)

    rvc_cli.cmd_feedback(target, letter, origin="rvc", cli_root=root)

    after = _config_lines(target)
    assert after == before, "self-ingest must not touch .rvc-root"
    assert os.path.exists(
        os.path.join(target, "00_INBOX", "BUG-01-FEEDBACK-rvc.md"))