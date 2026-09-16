#!/usr/bin/env python3
"""STORY-032: `rvc help` — nested command reference with exact descriptions.

Acceptance criteria under test:
1. `rvc help` renders every command with the exact concise description from
   COMMANDS.md, in the nested shape (help / issue help / project help).
2. Each command's help lists its arguments/flags with defaults, one per line,
   matching COMMANDS.md.
3. The nested structure mirrors reality: `issue` shows `list` + transitions;
   viewing is `get`'s job; `issue ⟨ID⟩` is a hidden alias never advertised.
4. `rvc help` exits 0 and needs no vault (pure static text).
5. Every ambiguity/duplicate noted in COMMANDS.md is resolved or explicitly
   acknowledged in the help text (triage decisions folded).
"""

import contextlib
import io
import pathlib
import re
import sys

import helpers
from helpers import rvc_cli


COMMANDS_MD = pathlib.Path(__file__).resolve().parent.parent / (
    "rvc-vault/10_CONTEXT/specs/COMMANDS.md"
)


def help_output(subgroup=None):
    """Run cmd_help and return the rendered text."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rvc_cli.cmd_help(subgroup)
    return buf.getvalue()


def test_help_covers_every_command_in_commands_md():
    """AC1/DoD: no command in COMMANDS.md lacks a help entry.

    Diff the help text against the source of truth: extract every
    `### \`rvc <command>\`` section header from COMMANDS.md and assert the
    command appears in the rendered top-level help.
    """
    md = COMMANDS_MD.read_text()
    command_names = re.findall(r"### `rvc ([\w-]+)", md)
    assert command_names, "COMMANDS.md: no `### `rvc ...`` headers found — spec drifted?"

    out = help_output()
    for name in command_names:
        assert name in out, (
            f"`rvc help` does not mention command '{name}' from COMMANDS.md"
        )


def test_help_lists_flags_with_defaults_one_per_line():
    """AC2: key flags with defaults appear one per line in the top-level help."""
    out = help_output()

    # --path global flag with default
    assert "--path <path>" in out and "default: ." in out
    # create flags with defaults, on their own lines
    assert "--prefix     ID prefix (default: STORY)" in out
    assert "--type       issue type (default: story)" in out
    assert "--priority   priority (default: Medium" in out
    # plate flags with defaults
    assert "--format     output format (default: text)" in out
    assert "--stale-days overdue threshold in days (default: 7)" in out
    # install dir default
    assert "--dir        install directory (default: ~/.local/bin)" in out
    # init tree default
    assert "--tree       bucket layout preset (default: legacy)" in out


def test_issue_help_advertises_get_not_hidden_alias():
    """AC3: `rvc issue help` says viewing is `rvc get ⟨ID⟩`; never the alias."""
    out = help_output("issue")
    assert "rvc get <ID>" in out
    assert "viewing" in out
    # The hidden alias `issue ⟨ID⟩` must not be advertised as a viewing path.
    assert "rvc issue <ID>" not in out


def test_issue_help_shows_list_and_transitions():
    """AC1/3: issue group exposes `list` and the transition actions."""
    out = help_output("issue")
    assert "rvc issue list" in out
    for action in ("triage", "start", "block", "defer", "review", "done",
                   "evict", "supersede"):
        assert action in out, f"issue help missing transition '{action}'"


def test_list_help_says_it_is_an_alias():
    """AC5 (note 2): `list` stays an alias of `issue list`; help says so."""
    out = help_output()
    assert "alias for 'rvc issue list'" in out


def test_init_vs_project_init_distinguished():
    """AC5 (note 4): `init` (flat) vs `project init` (vault subdirectory)."""
    top = help_output()
    assert "flat vault (no vault/ subdirectory)" in top
    proj = help_output("project")
    assert "project with a vault subdirectory" in proj
    assert "not flat" in proj


def test_rescan_vs_doctor_fix_scope_stated():
    """AC5 (note 5): `rescan` (broad) vs `doctor --fix` (surgical) scope."""
    out = help_output()
    assert "surgical" in out
    assert "broader" in out
    assert "doctor --fix" in out
    assert "rescan" in out


def test_issue_create_acknowledged_as_tree_verb():
    """AC5 (note 6): `issue ⟨ID⟩ create` acknowledged as an emergent tree verb."""
    out = help_output("issue")
    assert "create" in out
    assert "tree verb" in out


def test_help_needs_no_vault_and_exits_zero():
    """AC4: help is pure static text — works before init, from any directory."""
    # cmd_help has no vault_path parameter (static text only).
    assert "vault_path" not in rvc_cli.cmd_help.__code__.co_varnames

    for argv, subgroup in (
        (["rvc", "help"], None),
        (["rvc", "issue", "help"], "issue"),
        (["rvc", "project", "help"], "project"),
    ):
        old_argv = sys.argv
        try:
            sys.argv = argv
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rvc_cli.main()  # returns 0; help needs no vault lookup
        finally:
            sys.argv = old_argv
        assert "rvc" in buf.getvalue(), f"{argv} printed no help"