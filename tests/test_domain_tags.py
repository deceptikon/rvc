#!/usr/bin/env python3
"""BUG-14 acceptance tests: domain_tags become real.

AC1: trailing domain slug in filename: <PREFIX>-<ID>-<title>[<domain>].md
AC2: rvc create --domain <slug> stamps frontmatter and filename
AC3: rvc set <ID> --domain <slug> renames file and rewrites wikilinks
AC4: rvc context displays domain and inherits epic domain when story omits its own
AC5: rvc doctor flags filename/frontmatter domain mismatch
AC6: rvc plate shows a domain summary (a histogram, not a tag dump)
AC7: rvc plate validates tags against the vocabulary declared in .rvc-root (ask 3,
     relocated: checked at render time, never at create)
"""

import os

import helpers
from helpers import make_vault, read_frontmatter, rvc_cli, write_issue


def _declare_domains(vault, *slugs):
    """Declare a vocabulary in the vault's own `.rvc-root` — no second file."""
    with open(os.path.join(vault, ".rvc-root"), "a") as f:
        for slug in slugs:
            f.write(f"domain.{slug}={slug} coverage\n")


def _make_vault_with_domains():
    """Create a scratch vault and seed it with a controlled domain vocabulary."""
    root, vault = make_vault()
    _declare_domains(vault, "corpus", "infra", "review_queue", "legal_corpus")
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




def _write_raw(vault, rel_path, text):
    """Write a file verbatim — for frontmatter shapes the dict helper cannot express."""
    path = os.path.join(vault, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path


def _domain_block(out):
    """The DOMAINS section of a plate rendering, alone."""
    assert "DOMAINS" in out, out
    tail = out.split("\nDOMAINS", 1)[1]
    for marker in ("\nEXTERNAL FEEDBACK", "\nRECENT ACTIVITY"):
        tail = tail.split(marker, 1)[0]
    return tail


def test_plate_shows_domain_summary():
    """AC6: the plate's DOMAINS block is a histogram of slugs, not a tag dump."""
    _, vault = _make_vault_with_domains()
    rvc_cli.cmd_create_issue(
        vault, "Alpha", issue_type="story", priority="P1", domain="corpus")
    rvc_cli.cmd_create_issue(
        vault, "Beta", issue_type="story", priority="P1", domain="corpus")
    rvc_cli.cmd_create_issue(
        vault, "Gamma", issue_type="story", priority="P1", domain="infra")
    # Create one without a domain — not in the histogram, but counted
    rvc_cli.cmd_create_issue(
        vault, "Delta", issue_type="story", priority="P1")

    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert "corpus×2" in block, block
    assert "infra" in block, block
    assert "untagged (1):" in block, block
    # The noise this replaces: full file names and one group per raw tag string
    rows = [ln for ln in block.splitlines() if ln.strip() and "tagged" not in ln]
    assert not [ln for ln in rows if ".md" in ln or "[" in ln], rows
    # When declared vocabulary matches, healthy status is clean and quiet
    assert "undeclared" not in block, block


def test_plate_names_the_untagged_surfaces():
    """AC6: a count nobody can act on is not a finding; the ids are printed."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "No Domain At All", issue_type="story", priority="P1")
    item_id = read_frontmatter(path)["id"]
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert f"untagged (1): {item_id}" in block, block


def test_plate_validates_against_the_declared_vocabulary():
    """AC7: ask 3's teeth, at render time — an off-list slug is named, not refused."""
    _, vault = _make_vault_with_domains()
    rvc_cli.cmd_create_issue(vault, "On List", issue_type="story", priority="P1",
                             domain="corpus")
    rvc_cli.cmd_create_issue(vault, "Off List", issue_type="story", priority="P1",
                             domain="story")
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert "undeclared: story×1" in block, block
    assert "corpus" in block and "undeclared: corpus" not in block, block


def test_plate_says_when_no_vocabulary_is_declared():
    """AC7: absence of a check is stated, never mistaken for absence of a problem."""
    root, vault = make_vault()
    rvc_cli.cmd_create_issue(vault, "Anything", issue_type="story", priority="P1",
                             domain="whatever")
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert "vocabulary: none declared" in block, block


def test_read_domain_vocabulary_parses_the_marker():
    """AC7: `domain.<slug>=<label>` lines, comments ignored, absent means no list."""
    root, vault = make_vault()
    assert rvc_cli.read_domain_vocabulary(vault) == {}
    with open(os.path.join(vault, ".rvc-root"), "a") as f:
        f.write("# comment\ndomain.rvc=the tool\ndomain.plate = the plate\n")
    vocab = rvc_cli.read_domain_vocabulary(vault)
    assert vocab == {"rvc": "the tool", "plate": "the plate"}, vocab


def test_plate_groups_per_slug_not_per_tag_string():
    """AC6: a multi-tag issue joins every slug group it carries, counted once per slug."""
    _, vault = _make_vault_with_domains()
    _write_raw(vault, "20_NEXT/STORY-300-Alpha.md", """---
id: STORY-300
title: Alpha
type: story
priority: P1
domain_tags: ["corpus", "infra"]
---
""")
    _write_raw(vault, "20_NEXT/STORY-301-Beta.md", """---
id: STORY-301
title: Beta
type: story
priority: P1
domain_tags: [corpus, review_queue]
---
""")
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert "corpus×2" in block, block
    assert "infra" in block and "review_queue" in block, block
    assert "2/2 issues tagged" in block or "2 of 2 surfaces tagged" in block, block


def test_plate_reads_block_list_domain_tags():
    """AC6: the YAML block form (this vault's older shape) is not invisible."""
    _, vault = _make_vault_with_domains()
    _write_raw(vault, "20_NEXT/STORY-302-Gamma.md", """---
id: STORY-302
title: Gamma
type: story
priority: P1
domain_tags:
  - corpus
  - legal_corpus
---
""")
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert "corpus" in block and "legal_corpus" in block, block


def test_plate_json_domains_are_counted_slugs():
    """AC6+AC7: the JSON payload keeps the detail the text rendering folds away."""
    import json
    _, vault = _make_vault_with_domains()
    rvc_cli.cmd_create_issue(
        vault, "Alpha", issue_type="story", priority="P1", domain="corpus")
    rvc_cli.cmd_create_issue(
        vault, "Off List", issue_type="story", priority="P1", domain="pipeline")
    rvc_cli.cmd_create_issue(vault, "Bare", issue_type="story", priority="P1")
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault, fmt="json")
    domains = json.loads(out)["domains"]
    assert domains["tagged"] == 2 and domains["untagged"] == 1, domains
    assert domains["untagged_items"] == ["STORY-03"], domains
    assert domains["vocabulary"]["declared"] == 4, domains
    assert [row["domain"] for row in domains["undeclared"]] == ["pipeline"], domains
    corpus = [row for row in domains["slugs"] if row["domain"] == "corpus"][0]
    assert corpus["count"] == 1 and corpus["items"] == ["STORY-01"], domains


def test_create_never_refuses_an_undeclared_domain():
    """AC7: the vocabulary is a render-time check; a mint is never blocked on a slug."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Wild Slug", issue_type="story", priority="P1", domain="never_declared")
    assert os.path.exists(path)
    assert read_frontmatter(path).get("domain_tags") == "never_declared", path


def test_set_domain_replaces_block_list_cleanly():
    """AC3: rewriting a multi-line tag field must not orphan the old items."""
    _, vault = _make_vault_with_domains()
    path = _write_raw(vault, "20_NEXT/STORY-303-Delta.md", """---
id: STORY-303
title: Delta
type: story
priority: P1
domain_tags:
  - corpus
  - infra
---
""")
    new_path = rvc_cli.cmd_set_issue(vault, "STORY-303", domain="review_queue")
    assert not os.path.exists(path), "the slug stamp renamed the file"
    fm = open(new_path).read().split("---")[1]
    assert "domain_tags: review_queue" in fm, fm
    assert "- corpus" not in fm and "- infra" not in fm, fm


def test_set_multiple_domains_writes_list_and_stamps_primary():
    """AC1+AC3: `--domain "a, b"` keeps both slugs; the filename carries the first."""
    _, vault = _make_vault_with_domains()
    path = rvc_cli.cmd_create_issue(
        vault, "Multi", issue_type="story", priority="P1", domain="corpus, infra")
    assert os.path.basename(path).endswith("[corpus].md"), path
    assert read_frontmatter(path).get("domain_tags") == "[corpus, infra]", path
    assert rvc_cli.frontmatter_domain_tags(open(path).read()) == ["corpus", "infra"]


def test_set_priority_alone_never_renames():
    """AC3: only the domain slug is mutable in the name — a hand-named file survives."""
    _, vault = _make_vault_with_domains()
    path = _write_raw(vault, "20_NEXT/STORY-304-Hand Named File.md", """---
id: STORY-304
title: A title that does not match the file name
type: story
priority: P1
---
""")
    assert rvc_cli.cmd_set_issue(vault, "STORY-304", priority="P0") == path
    assert os.path.exists(path)


def test_doctor_multi_tag_slug_is_not_drift():
    """AC5: the name carries the primary slug — agreement is membership, not string equality."""
    _, vault = _make_vault_with_domains()
    _write_raw(vault, "20_NEXT/STORY-305-Probe[corpus].md", """---
id: STORY-305
title: Probe
type: story
priority: P1
domain_tags: [corpus, infra]
---
""")
    report = rvc_cli.cmd_doctor(vault)
    drift = [w for w in report["warnings"] if "mismatch" in w.lower()]
    assert not drift, report["warnings"]


def test_doctor_aggregates_files_without_a_slug():
    """AC5: pre-migration state is one line for the tree, not one warning per file."""
    _, vault = _make_vault_with_domains()
    for n in range(4):
        _write_raw(vault, "20_NEXT/STORY-31%d-Probe.md" % n, """---
id: STORY-31%d
title: Probe
type: story
priority: P1
domain_tags: corpus
---
""" % n)
    report = rvc_cli.cmd_doctor(vault)
    slug_lines = [w for w in report["warnings"] if "no slug in filename" in w.lower()]
    assert len(slug_lines) == 1, report["warnings"]
    assert "4 files" in slug_lines[0], slug_lines[0]


def _marker_text(vault):
    with open(os.path.join(vault, ".rvc-root")) as f:
        return f.read()


def _marker_domains(vault):
    """{slug: label} as written in the marker right now (parser-free read)."""
    out = {}
    for line in _marker_text(vault).splitlines():
        if line.startswith("domain.") and "=" in line:
            key, _, label = line.partition("=")
            out[key[len("domain."):] ] = label
    return out


def test_doctor_writes_the_vocabulary_from_the_tree():
    """AC7: the list is generated by the audit, so it cannot be a second source of truth."""
    root, vault = make_vault()          # no hand-kept vocabulary at all
    rvc_cli.cmd_create_issue(vault, "Alpha", issue_type="story", priority="P1", domain="corpus")
    rvc_cli.cmd_create_issue(vault, "Beta", issue_type="story", priority="P1", domain="corpus")
    rvc_cli.cmd_create_issue(vault, "Gamma", issue_type="story", priority="P1", domain="infra")
    report = rvc_cli.cmd_doctor(vault)
    declared = _marker_domains(vault)
    assert sorted(declared) == ["corpus", "infra"], declared
    assert report["domains"]["declared"] == ["corpus", "infra"], report["domains"]
    assert report["domains"]["written"] is True, report["domains"]


def test_doctor_keeps_type_as_tag_out_and_names_the_files():
    """AC7: a type is what an issue IS, never the domain it changes."""
    root, vault = make_vault()
    rvc_cli.cmd_create_issue(vault, "Tagged With Its Own Type", issue_type="story",
                             priority="P1", domain="story")
    report = rvc_cli.cmd_doctor(vault)
    assert "story" not in _marker_domains(vault), _marker_domains(vault)
    assert "story" in report["domains"]["dropped"], report["domains"]
    assert any("type-as-tag" in w for w in report["warnings"]), report["warnings"]


def test_doctor_folds_spelling_variants_to_the_commonest():
    """AC7: `review-queue` and `review_queue` are one domain spelled twice."""
    root, vault = make_vault()
    _write_raw(vault, "20_NEXT/STORY-400-A.md", """---
id: STORY-400
title: A
type: story
priority: P1
domain_tags: review-queue
---
""")
    for n in (401, 402):
        _write_raw(vault, f"20_NEXT/STORY-{n}-B.md", f"""---
id: STORY-{n}
title: B{n}
type: story
priority: P1
domain_tags: review_queue
---
""")
    report = rvc_cli.cmd_doctor(vault)
    declared = _marker_domains(vault)
    assert list(declared) == ["review_queue"], declared
    assert report["domains"]["folded"] == {"review_queue": ["review-queue"]}, report["domains"]
    assert any("variant" in w for w in report["warnings"]), report["warnings"]


def test_doctor_preserves_the_human_label_and_is_idempotent():
    """AC7: the label after `=` is the human's; the rest is a rendering."""
    root, vault = make_vault()
    _write_raw(vault, "20_NEXT/STORY-410-A.md", """---
id: STORY-410
title: A
type: story
priority: P1
domain_tags: corpus
---
""")
    with open(os.path.join(vault, ".rvc-root"), "a") as f:
        f.write("domain.corpus=Corpus scope and ingestion\n")
    first = rvc_cli.cmd_doctor(vault)
    assert first["domains"]["written"] is True, first["domains"]
    assert _marker_domains(vault) == {"corpus": "Corpus scope and ingestion"}, _marker_domains(vault)
    text = _marker_text(vault)
    second = rvc_cli.cmd_doctor(vault)
    assert second["domains"]["written"] is False, second["domains"]
    assert _marker_text(vault) == text, "a rebuild of a rebuild writes nothing"


def test_doctor_alias_rules_a_slug_away_and_the_plate_shows_where_it_goes():
    """AC7: the human half — `domain-alias.<rejected>=<kept>` is a ruling, not a duplicate."""
    root, vault = make_vault()
    _declare_domains(vault, "review_queue")
    with open(os.path.join(vault, ".rvc-root"), "a") as f:
        f.write("domain-alias.citation=review_queue\n")
    _write_raw(vault, "20_NEXT/STORY-420-A.md", """---
id: STORY-420
title: A
type: story
priority: P1
domain_tags: citation
---
""")
    report = rvc_cli.cmd_doctor(vault)
    assert report["domains"]["absorbed"] == {"citation": "review_queue"}, report["domains"]
    assert "citation" not in _marker_domains(vault), _marker_domains(vault)
    assert "review_queue" in _marker_domains(vault), _marker_domains(vault)
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert "undeclared: citation×1→review_queue" in block, block


def test_doctor_ignores_archived_and_closed_tags():
    """AC7: an archive is evidence, the done lane is history — neither votes on the list."""
    root, vault = make_vault()
    _write_raw(vault, "90_ARCHIVE/done/STORY-430-A.md", """---
id: STORY-430
title: A
type: story
priority: P1
domain_tags: retired_domain
---
""")
    _write_raw(vault, "60_DONE/STORY-431-B.md", """---
id: STORY-431
title: B
type: story
priority: P1
domain_tags: finished_domain
---
""")
    rvc_cli.cmd_doctor(vault)
    assert _marker_domains(vault) == {}, _marker_domains(vault)


def test_doctor_keeps_a_labeled_domain_and_drops_an_unlabeled_leftover():
    """AC7: a label is a claim; an unlabelled leftover of an older census evaporates."""
    root, vault = make_vault()
    _write_raw(vault, "20_NEXT/STORY-440-A.md", """---
id: STORY-440
title: A
type: story
priority: P1
domain_tags: corpus
---
""")
    with open(os.path.join(vault, ".rvc-root"), "a") as f:
        f.write("domain.ai_watch=regulatory feed, no open work yet\ndomain.dead_verb=\n")
    report = rvc_cli.cmd_doctor(vault)
    declared = _marker_domains(vault)
    assert "ai_watch" in declared, declared          # standing by its label
    assert "dead_verb" not in declared, declared     # nothing open, nothing claimed
    assert report["domains"]["standing"] == ["ai_watch"], report["domains"]


def test_untagged_non_issue_surfaces_are_counted_not_listed():
    """AC6: non-issues (essays, letters) are not expected to carry domain tags."""
    _, vault = _make_vault_with_domains()
    rvc_cli.cmd_create_issue(vault, "Tagged", issue_type="story", priority="P1", domain="corpus")
    _write_raw(vault, "50_DEFERRED/ESSAY--Pilot-and-Guard.md", """---
title: Pilot and Guard
type: essay
---
""")
    _write_raw(vault, "00_INBOX/FEEDBACK-rvc.md", """---
title: A letter
type: feedback
---
""")
    _, out = helpers.capture_stdout(rvc_cli.cmd_plate, vault)
    block = _domain_block(out)
    assert "1/1 issues tagged" in block, block
    assert "untagged" not in block, block
    assert "ESSAY" not in block and "FEEDBACK" not in block, block


def test_doctor_refresh_leaves_the_rest_of_the_marker_alone():
    """The marker also carries the tree map and the mint floors — a refresh may not touch them."""
    root, vault = make_vault()
    with open(os.path.join(vault, ".rvc-root"), "a") as f:
        f.write("mint.STORY=77\nplate.owner=@boss\n")
    _write_raw(vault, "20_NEXT/STORY-450-A.md", """---
id: STORY-450
title: A
type: story
priority: P1
domain_tags: corpus
---
""")
    rvc_cli.cmd_doctor(vault)
    text = _marker_text(vault)
    assert "mint.STORY=77" in text, text
    assert "plate.owner=@boss" in text, text
    assert "tree.start=30_ACTIVE" in text, text
    assert "vault=scratch" in text, text
    assert rvc_cli.resolve_tree(vault)["start"] == "30_ACTIVE", text


def test_doctor_lets_the_closed_lane_keep_its_names():
    """AC5: a done issue is evidence. Stamping its filename is churn no reader needs."""
    _, vault = make_vault()
    _write_raw(vault, "60_DONE/STORY-460-Closed.md", """---
id: STORY-460
title: Closed
type: story
priority: P1
domain_tags: corpus
---
""")
    _write_raw(vault, "20_NEXT/STORY-461-Open.md", """---
id: STORY-461
title: Open
type: story
priority: P1
domain_tags: corpus
---
""")
    report = rvc_cli.cmd_doctor(vault)
    slug_lines = [w for w in report["warnings"] if "no slug in filename" in w.lower()]
    assert len(slug_lines) == 1, report["warnings"]
    assert "STORY-461" in slug_lines[0] and "STORY-460" not in slug_lines[0], slug_lines[0]
