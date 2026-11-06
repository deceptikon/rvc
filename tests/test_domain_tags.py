#!/usr/bin/env python3
"""BUG-14 acceptance tests: domain_tags become real.

AC1: trailing domain slug in filename: <PREFIX>-<ID>-<title>[<domain>].md
AC2: rvc create --domain <slug> stamps frontmatter and filename
AC3: rvc set <ID> --domain <slug> renames file and rewrites wikilinks
AC4: rvc context displays domain and inherits epic domain when story omits its own
AC5: rvc doctor flags filename/frontmatter domain mismatch
AC6: rvc plate shows domain summary
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


def test_create_without_domain_succeeds():
    """AC2: creating without --domain is always allowed (no mandatory governance)."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Platform Epic", issue_type="epic", priority="P1")
    fm = read_frontmatter(path)
    assert "domain_tags" not in fm, fm


def test_create_story_with_epic_no_domain_succeeds():
    """Creating a story with an epic but no domain of its own works."""
    _, vault = _make_vault_with_domains()
    epic_path = rvc_cli.cmd_create_issue(
        vault, "Platform Epic", issue_type="epic", priority="P1", domain="infra")
    epic_fm = read_frontmatter(epic_path)
    epic_id = epic_fm["id"]
    story_path = rvc_cli.cmd_create_issue(
        vault, "Child Story", issue_type="story", priority="P1", epic=epic_id)
    assert os.path.basename(story_path).startswith("STORY-")


def test_create_with_domain_puts_slug_at_end():
    """AC1+AC2: domain slug sits at end of filename before .md."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Refactor Parser", issue_type="story", priority="P1", domain="corpus")
    basename = os.path.basename(path)
    assert basename.endswith("[corpus].md"), f"got {basename}"
    assert basename.startswith("STORY-"), f"got {basename}"
    fm = read_frontmatter(path)
    assert fm.get("domain_tags") == "corpus", fm


def test_set_changes_domain_and_renames_file():
    """AC3: rvc set changes domain and rewrites filename + frontmatter."""
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
    """AC3: rvc set updates epic and priority without rename."""
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


def test_set_output_shows_changes():
    """AC3: rvc set prints a summary of what changed."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Alpha", issue_type="story", priority="P1", domain="corpus")
    story_id = read_frontmatter(path)["id"]
    _, out = helpers.capture_stdout(
        rvc_cli.cmd_set_issue, vault, story_id, priority="P0", domain="infra")
    assert "Updated" in out, out
    assert story_id in out, out
    assert "domain" in out or "priority" in out or "renamed" in out, out


def test_context_shows_domain():
    """AC4: context target summary includes domain tag."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Visible Domain", issue_type="story", priority="P1", domain="review_queue")
    item_id = read_frontmatter(path)["id"]
    _, out = helpers.capture_stdout(rvc_cli.cmd_context, vault, item_id,
                                    budget=40000, mode="summary")
    assert "review_queue" in out, out


def test_context_inherits_epic_domain():
    """AC4: story without domain inherits epic domain in context display."""
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
    """AC5: filename slug disagrees with frontmatter domain_tags is a warning."""
    _, vault = _make_vault_with_domains()
    write_issue(vault, "20_NEXT/STORY-500-Probe[corpus].md",
                {"id": "STORY-500", "type": "story", "priority": "P1",
                 "domain_tags": "infra"})
    report = rvc_cli.cmd_doctor(vault)
    found = any("domain" in w.lower() for w in report["warnings"])
    assert found, f"expected domain warning, got {report['warnings']}"


def test_doctor_flags_missing_frontmatter_domain():
    """AC5: filename has domain slug but no frontmatter domain_tags is a warning."""
    _, vault = _make_vault_with_domains()
    write_issue(vault, "20_NEXT/STORY-501-Probe[corpus].md",
                {"id": "STORY-501", "type": "story", "priority": "P1"})
    report = rvc_cli.cmd_doctor(vault)
    found = any("no domain_tags" in w.lower() for w in report["warnings"])
    assert found, f"expected missing frontmatter domain warning, got {report['warnings']}"


def test_doctor_flags_missing_slug_in_filename():
    """AC5: frontmatter has domain_tags but no slug in filename is a warning."""
    _, vault = _make_vault_with_domains()
    write_issue(vault, "20_NEXT/STORY-502-Probe.md",
                {"id": "STORY-502", "type": "story", "priority": "P1",
                 "domain_tags": "corpus"})
    report = rvc_cli.cmd_doctor(vault)
    found = any("no slug" in w.lower() for w in report["warnings"])
    assert found, f"expected missing slug warning, got {report['warnings']}"


def test_plate_shows_domain_summary():
    """AC6: rvc plate includes a DOMAINS section with domain groupings."""
    _, vault = _make_vault_with_domains()
    rvc_cli.cmd_create_issue(
        vault, "Alpha", issue_type="story", priority="P1", domain="corpus")
    rvc_cli.cmd_create_issue(
        vault, "Beta", issue_type="story", priority="P1", domain="corpus")
    rvc_cli.cmd_create_issue(
        vault, "Gamma", issue_type="story", priority="P1", domain="infra")
    # Create one without domain — not in summary
    rvc_cli.cmd_create_issue(
        vault, "Delta", issue_type="story", priority="P1")

    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    assert "DOMAINS" in out, out
    assert "corpus" in out, out
    assert "infra" in out, out
    # Count of corpus items (2) should be present
    assert "(2)" in out, out