#!/usr/bin/env python3
"""STORY-130: `rvc create --body` must not duplicate the H1.

A body that opens with its own `# Heading` used to render twice: the CLI emits
its canonical `# <ID>: <title>` and appended the body verbatim. The redundant
leading H1 is stripped; the canonical heading always wins.
"""

from helpers import make_vault, rvc_cli


def h1_lines(content):
    """All markdown H1 lines (a line starting with `# `) in the rendered file."""
    return [ln for ln in content.splitlines() if ln.startswith("# ")]


def test_body_with_leading_h1_renders_once():
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(
        vault, "Body Probe", priority="P1",
        body="# My Own Title\n\nSome context here.")
    content = open(path).read()
    lines = h1_lines(content)
    assert lines == ["# STORY-01: Body Probe"], f"headings rendered:\n{lines}\n{content}"
    assert "Some context here." in content
    assert "My Own Title" not in content, "redundant body H1 must be stripped"


def test_body_without_heading_unaffected():
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(
        vault, "Plain Probe", priority="P1", body="Just some text.")
    content = open(path).read()
    assert h1_lines(content) == ["# STORY-01: Plain Probe"]
    assert "Just some text." in content


def test_body_with_only_a_heading_leaves_no_heading_duplicate():
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(
        vault, "Head Only Probe", priority="P1", body="# Only Heading")
    content = open(path).read()
    assert h1_lines(content) == ["# STORY-01: Head Only Probe"]


def test_body_with_subheading_is_kept():
    _, vault = make_vault()
    path = rvc_cli.cmd_create_issue(
        vault, "Sub Probe", priority="P1", body="## Notes\n\ntext")
    content = open(path).read()
    assert h1_lines(content) == ["# STORY-01: Sub Probe"]
    assert content.count("## Notes") == 1, "a `##` body heading must survive"