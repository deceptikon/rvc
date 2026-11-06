#!/usr/bin/env python3
"""BUG-14 acceptance tests: domain_tags become real.

AC1: trailing domain slug in filename: <PREFIX>-<ID>-<title>[<domain>].md
AC2: mandatory ownership — epics require domain; stories require domain or epic
AC3: rvc create --domain <slug> stamps frontmatter and filename
AC4: rvc set <ID> --domain <slug> renames file and rewrites wikilinks
AC5: rvc context displays domain and inherits epic domain when story omits its own
AC6: rvc doctor flags domain mismatch and unknown domains
"""

import os

import helpers
from helpers import make_vault, read_frontmatter, rvc_cli, write_issue


def _make_vault_with_domains():
    """Create a scratch vault and seed it with a controlled domain vocabulary."""
    root, vault = make_vault()
    vocab_path = os.path.join(vault, "10_CONTEXT", "specs", "Story-Domains.md")
    os.makedirs(os.path.dirname(vocab_path), exist_ok=True)
    with open(vocab_path, "w") as f:
        f.write("# Story Domains\n\n- corpus\n- infra\n- review_queue\n- legal_corpus\n")
    return root, vault


def test_create_epic_without_domain_fails():
    """AC2: epic requires domain at creation time when a vocabulary exists."""
    _, vault = _make_vault_with_domains()
    try:
        rvc_cli.cmd_create_issue(vault, "Platform Epic", issue_type="epic", priority="P1")
    except SystemExit as e:
        assert e.code == 1
    else:
        raise AssertionError("expected SystemExit for epic without domain")


def test_create_story_without_domain_or_epic_fails():
    """AC2: story requires domain or epic at creation time when a vocabulary exists."""
    _, vault = _make_vault_with_domains()
    try:
        rvc_cli.cmd_create_issue(vault, "Orphan Story", issue_type="story", priority="P1")
    except SystemExit as e:
        assert e.code == 1
    else:
        raise AssertionError("expected SystemExit for story without domain or epic")


def test_create_story_with_epic_no_domain_succeeds():
    """AC2: story with epic but no domain of its own is allowed."""
    _, vault = _make_vault_with_domains()
    epic_path = rvc_cli.cmd_create_issue(
        vault, "Platform Epic", issue_type="epic", priority="P1", domain="infra")
    epic_fm = read_frontmatter(epic_path)
    epic_id = epic_fm["id"]
    story_path = rvc_cli.cmd_create_issue(
        vault, "Child Story", issue_type="story", priority="P1", epic=epic_id)
    assert os.path.basename(story_path).startswith("STORY-")


def test_create_with_domain_puts_slug_at_end():
    """AC1+AC3: domain slug sits at end of filename before .md."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Refactor Parser", issue_type="story", priority="P1", domain="corpus")
    basename = os.path.basename(path)
    assert basename.endswith("[corpus].md"), f"got {basename}"
    assert basename.startswith("STORY-"), f"got {basename}"
    fm = read_frontmatter(path)
    assert fm.get("domain_tags") == "corpus", fm


def test_set_changes_domain_and_renames_file():
    """AC4: rvc set changes domain and rewrites filename + frontmatter."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Refactor Parser", issue_type="story", priority="P1", domain="corpus")
    old_name = os.path.basename(path)
    story_id = read_frontmatter(path)["id"]

    # Seed a backlink pointing at the old filename (no extension)
    backlink_path = os.path.join(vault, "20_NEXT", "LINKED.md")
    write_issue(vault, "20_NEXT/LINKED.md",
                {"id": "STORY-99", "type": "story", "priority": "P1"},
                body=f"See [[{old_name[:-3]}]]")

    new_path = rvc_cli.cmd_set_issue(vault, story_id, domain="infra")

    basename = os.path.basename(new_path)
    assert basename == old_name.replace("[corpus]", "[infra]"), f"got {basename}"
    assert not os.path.exists(path), "old path should be gone after rename"
    fm = read_frontmatter(new_path)
    assert fm.get("domain_tags") == "infra", fm

    # backlink rewritten
    linked_text = open(backlink_path).read()
    assert f"[[{os.path.basename(new_path)[:-3]}]]" in linked_text


def test_set_can_change_epic_and_priority():
    """AC4: rvc set updates epic and priority without rename."""
    _, vault = _make_vault_with_domains()
    epic_path = rvc_cli.cmd_create_issue(
        vault, "Parent Epic", issue_type="epic", priority="P1", domain="infra")
    epic_id = read_frontmatter(epic_path)["id"]

    story_path = rvc_cli.cmd_create_issue(
        vault, "Child Story", issue_type="story", priority="P1", domain="corpus")
    story_id = read_frontmatter(story_path)["id"]

    rvc_cli.cmd_set_issue(vault, story_id, epic=epic_id, priority="P2")
    fm = read_frontmatter(story_path)
    assert fm.get("epic") == f"[[{epic_id}]]", fm
    assert fm.get("priority") == "P2", fm


def test_context_shows_domain():
    """AC5: context target summary includes domain tag."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Visible Domain", issue_type="story", priority="P1", domain="review_queue")
    item_id = read_frontmatter(path)["id"]
    _, out = helpers.capture_stdout(rvc_cli.cmd_context, vault, item_id,
                                    budget=40000, mode="summary")
    assert "review_queue" in out, out


def test_context_inherits_epic_domain():
    """AC5: story without domain inherits epic domain in context display."""
    _, vault = _make_vault_with_domains()
    epic_path = rvc_cli.cmd_create_issue(
        vault, "Parent Epic", issue_type="epic", priority="P1", domain="corpus")
    epic_id = read_frontmatter(epic_path)["id"]

    story_path = rvc_cli.cmd_create_issue(
        vault, "Orphan with Epic", issue_type="story", priority="P1", epic=epic_id)
    story_id = read_frontmatter(story_path)["id"]

    fm = read_frontmatter(story_path)
    assert "domain_tags" not in fm, fm

    _, out = helpers.capture_stdout(rvc_cli.cmd_context, vault, story_id,
                                    budget=40000, mode="summary")
    assert "corpus" in out, out


def test_doctor_flags_domain_mismatch():
    """AC6: filename slug disagrees with frontmatter domain_tags is a warning."""
    _, vault = _make_vault_with_domains()
    write_issue(vault, "20_NEXT/STORY-500-Probe[corpus].md",
                {"id": "STORY-500", "type": "story", "priority": "P1",
                 "domain_tags": "infra"})
    report = rvc_cli.cmd_doctor(vault)
    found = any("domain" in w.lower() for w in report["warnings"])
    assert found, f"expected domain warning, got {report['warnings']}"


def test_doctor_flags_unknown_domain():
    """AC6: domain not in Story-Domains.md is a warning."""
    _, vault = _make_vault_with_domains()
    write_issue(vault, "20_NEXT/STORY-501-Probe[unknown].md",
                {"id": "STORY-501", "type": "story", "priority": "P1",
                 "domain_tags": "unknown"})
    report = rvc_cli.cmd_doctor(vault)
    found = any("unknown" in w.lower() or "domain" in w.lower() for w in report["warnings"])
    assert found, f"expected unknown domain warning, got {report['warnings']}"
