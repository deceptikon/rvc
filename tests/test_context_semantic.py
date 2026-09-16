#!/usr/bin/env python3
"""STORY-033: `rvc context` — zero-dependency semantic retrieval.

Acceptance criteria under test:
1. BM25/TF-IDF ranking over vault docs (tokenization, stopwords, heading and
   frontmatter boosts, kebab-case ids, unpadded numerals).
2. Incremental `.rvc-context-cache.json`: identity is the Document ID, a moved
   file repaths without re-tokenization, corrupt caches self-heal, `--reindex`
   forces a rebuild.
3. Hybrid assembly: target + deduplicated hard `[[wikilinks]]` + Top-K soft
   matches, with the soft set excluding the target and already-linked docs.
4. Budget trimming: output never exceeds `--budget`, with a truncation notice.
5. ID normalization: `STORY-33` resolves `STORY-033` in `find_file_by_id`.
6. MCP daemon surface: `rvc_get_context` grows top_k/budget_chars/include_semantic.
"""

import ast
import json
import os
import pathlib
import tempfile
import time

import helpers
from helpers import capture_stdout, make_vault, rvc_cli, write_issue

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def write_doc(vault, rel_path, text):
    """Plain (non-issue) markdown doc for retrieval fixtures."""
    path = os.path.join(vault, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return path


class index_spy:
    """Context manager counting `_context_index_doc` calls (re-tokenizations)."""

    def __enter__(self):
        self.calls = []
        self._orig = rvc_cli._context_index_doc

        def spy(cache, vault, rel_path, text, mtime, size):
            self.calls.append(rel_path)
            return self._orig(cache, vault, rel_path, text, mtime, size)

        rvc_cli._context_index_doc = spy
        return self

    def __exit__(self, *exc):
        rvc_cli._context_index_doc = self._orig
        return False


# ── AC1: tokenization & ranking ──────────────────────────────────────────────

def test_tokenizer_boosts_title_tags_and_headings():
    """Headings 2x, H1/title/id 3x, tags 2.5x, body 1x (AC1)."""
    assert rvc_cli._context_chunk_terms("# flock")["flock"] == 3.0
    assert rvc_cli._context_chunk_terms("## flock")["flock"] == 2.0
    assert rvc_cli._context_chunk_terms("flock")["flock"] == 1.0
    fm = "---\ntitle: flock\nid: flock\ntags: [flock]\n---\n"
    assert rvc_cli._context_chunk_terms(fm)["flock"] == 3.0 + 3.0 + 2.5


def test_tokenizer_kebab_ids_and_zero_padding():
    """`STORY-013` canonicalizes to `story-13`; parts are indexed too (AC1)."""
    terms = rvc_cli._context_terms("STORY-013 and STORY-13 both resolve")
    assert terms["story-13"] >= 2.0
    assert "story" in terms and "13" in terms
    # `pull_request` style identifiers split as well.
    assert "pull" in rvc_cli._context_terms("see pull_request here")


def test_stopwords_are_dropped():
    terms = rvc_cli._context_terms("the and of flock")
    assert terms.get("flock") == 1.0
    for stop in ("the", "and", "of"):
        assert stop not in terms


def test_bm25_prefers_term_match():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/ALPHA.md", "# Alpha\n\nflock concurrency lock\n")
    write_doc(vault, "10_CONTEXT/BETA.md", "# Beta\n\npasta recipes cooking\n")
    cache = rvc_cli.context_cache_update(vault, force=True)
    ranked = rvc_cli.context_rank(cache, {"flock": 3.0}, top_k=2,
                                  tree=rvc_cli.resolve_tree(vault))
    assert ranked, "no ranked results"
    assert ranked[0][3] == "10_CONTEXT/ALPHA.md"
    assert "flock" in [t.lower() for t in ranked[0][2]]


def test_bm25_length_normalization_bounds_long_docs():
    """A long noise doc must not outrank a short precise match (b=1.0)."""
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/SHORT.md", "# Short\n\nflock\n")
    write_doc(vault, "10_CONTEXT/LONG.md", "# Long\n\n" + "alpha " * 800 + "\nflock\n")
    cache = rvc_cli.context_cache_update(vault, force=True)
    ranked = rvc_cli.context_rank(cache, {"flock": 3.0}, top_k=2,
                                  tree=rvc_cli.resolve_tree(vault))
    assert ranked[0][3] == "10_CONTEXT/SHORT.md"


def test_archive_buckets_are_never_soft_suggestions():
    _, vault = make_vault()
    write_doc(vault, "90_ARCHIVE/done/STORY-009-Dead.md", "# Dead\n\nflock\n")
    write_doc(vault, "10_CONTEXT/LIVE.md", "# Live\n\nalpha beta\n")
    cache = rvc_cli.context_cache_update(vault, force=True)
    ranked = rvc_cli.context_rank(cache, {"flock": 3.0}, top_k=3,
                                  tree=rvc_cli.resolve_tree(vault))
    assert all(r[3] != "90_ARCHIVE/done/STORY-009-Dead.md" for r in ranked)


# ── AC2 & AC5: cache freshness, identity, id normalization ───────────────────

def test_find_file_by_id_accepts_unpadded_numerals():
    _, vault = make_vault()
    path = write_issue(vault, "20_NEXT/STORY-033-RVC-Context.md",
                       {"id": "STORY-033", "title": "Context"})
    assert rvc_cli.find_file_by_id(vault, "STORY-033") == path
    assert rvc_cli.find_file_by_id(vault, "STORY-33") == path
    assert rvc_cli.find_file_by_id(vault, "story-33") == path
    assert rvc_cli.find_file_by_id(vault, "STORY-34") is None


def test_cache_builds_on_missing_and_skips_clean_runs():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/A.md", "# A\n\nalpha\n")
    cache_path = rvc_cli.context_cache_path(vault)
    assert not os.path.exists(cache_path)
    rvc_cli.context_cache_update(vault)
    assert os.path.exists(cache_path)
    with index_spy() as spy:
        rvc_cli.context_cache_update(vault)
    assert spy.calls == [], "clean run re-tokenized documents"


def test_corrupt_cache_self_heals_without_error():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/A.md", "# A\n\nalpha\n")
    rvc_cli.context_cache_update(vault, force=True)
    with open(rvc_cli.context_cache_path(vault), "w") as f:
        f.write("{ definitely not json")
    cache = rvc_cli.context_cache_update(vault)
    assert "A" in cache["docs"]
    # Structurally invalid JSON (valid parse, wrong shape) also rebuilds.
    with open(rvc_cli.context_cache_path(vault), "w") as f:
        json.dump({"version": rvc_cli.CONTEXT_CACHE_VERSION, "docs": []}, f)
    cache = rvc_cli.context_cache_update(vault)
    assert "A" in cache["docs"]


def test_only_changed_documents_are_reindexed():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/A.md", "# A\n\nalpha\n")
    write_doc(vault, "10_CONTEXT/B.md", "# B\n\nbeta\n")
    rvc_cli.context_cache_update(vault, force=True)
    with index_spy() as spy:
        write_doc(vault, "10_CONTEXT/A.md", "# A\n\nalpha changed\n")
        rvc_cli.context_cache_update(vault)
    assert spy.calls == ["10_CONTEXT/A.md"]


def test_move_repaths_without_retokenize():
    _, vault = make_vault()
    write_doc(vault, "20_NEXT/STORY-007-Thing.md", "# Seven\n\nflock\n")
    cache = rvc_cli.context_cache_update(vault, force=True)
    before = list(cache["postings"]["flock"]["STORY-007"])
    new_rel = "60_DONE/STORY-007-Thing.md"
    os.makedirs(os.path.join(vault, "60_DONE"), exist_ok=True)
    os.rename(os.path.join(vault, "20_NEXT/STORY-007-Thing.md"),
              os.path.join(vault, new_rel))
    with index_spy() as spy:
        cache = rvc_cli.context_cache_update(vault)
    assert spy.calls == [], "a moved file was re-tokenized"
    assert cache["docs"]["STORY-007"]["path"] == new_rel
    assert cache["postings"]["flock"]["STORY-007"] == before


def test_reindex_forces_full_rebuild():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/A.md", "# A\n")
    write_doc(vault, "10_CONTEXT/B.md", "# B\n")
    rvc_cli.context_cache_update(vault, force=True)
    with index_spy() as spy:
        rvc_cli.context_cache_update(vault, force=True)
    assert sorted(spy.calls) == ["10_CONTEXT/A.md", "10_CONTEXT/B.md"]


def test_create_and_transition_hooks_keep_cache_warm():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/A.md", "# A\n\nalpha\n")
    rvc_cli.context_cache_update(vault, force=True)
    capture_stdout(rvc_cli.cmd_create_issue, vault, title="Probe")
    cache = rvc_cli._context_load_cache(vault)
    assert any(meta["path"].startswith("00_INBOX/") for meta in cache["docs"].values())
    created = next(meta["path"] for meta in cache["docs"].values()
                   if meta["path"].startswith("00_INBOX/"))
    write_issue(vault, "20_NEXT/STORY-005-Thing.md",
                {"id": "STORY-005", "title": "Thing"}, "flock")
    rvc_cli.context_cache_update(vault)
    capture_stdout(rvc_cli.cmd_issue_action, vault, "STORY-005", "done")
    cache = rvc_cli._context_load_cache(vault)
    assert cache["docs"]["STORY-005"]["path"] == "60_DONE/STORY-005-Thing.md"
    assert created  # silence unused warning


# ── AC3: hybrid assembly ─────────────────────────────────────────────────────

def test_context_assembles_target_hard_and_soft():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/HARD.md", "# Hard\n\nlinked reference text\n")
    write_issue(vault, "20_NEXT/STORY-001-Target.md",
                {"id": "STORY-001", "title": "Target"},
                "## Context\n\nzanzibar flock\n\n[[HARD]]\n")
    write_doc(vault, "10_CONTEXT/SOFT.md", "# Soft\n\nzanzibar flock notes\n")
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "STORY-001")
    assert "# RVC Context Assembler: STORY-001 (Target)" in out
    assert "## 1. Target Issue" in out
    assert "--- REFERENCE: [[HARD]] ---" in out
    assert "linked reference text" in out
    assert "## 3. Discovered Related Context" in out
    assert "10_CONTEXT/SOFT.md" in out
    assert "Matched terms:" in out
    assert "Relevance Score:" in out


def test_hard_links_deduplicated_and_excluded_from_soft():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/HARD.md", "# Hard\n\nflock flock flock\n")
    write_issue(vault, "20_NEXT/STORY-001-Target.md",
                {"id": "STORY-001", "title": "Target"},
                "## Context\n\nflock\n\n[[HARD]] [[HARD]] [[HARD#anchor|alias]]\n")
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "STORY-001")
    assert out.count("--- REFERENCE: [[HARD]] ---") == 1
    assert "RELATED: [[10_CONTEXT/HARD.md]]" not in out


def test_no_semantic_keeps_legacy_hard_links_only():
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/REL.md", "# Rel\n\nzanzibar zanzibar\n")
    write_issue(vault, "20_NEXT/STORY-001-Target.md",
                {"id": "STORY-001", "title": "Target"},
                "## Context\n\nzanzibar\n")
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "STORY-001", no_semantic=True)
    assert "Discovered Related Context" not in out
    assert "10_CONTEXT/REL.md" not in out
    _, full = capture_stdout(rvc_cli.cmd_context, vault, "STORY-001")
    assert "10_CONTEXT/REL.md" in full


def test_summary_mode_extracts_goal_and_acceptance():
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-001-Target.md",
                {"id": "STORY-001", "title": "Target"},
                "## Goal\n\ngoal text here\n\n## Acceptance Criteria\n\n- [ ] a thing\n\n"
                "## Noise\n\n" + "noise " * 500)
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "STORY-001", mode="summary")
    assert "goal text here" in out
    assert "- [ ] a thing" in out
    assert "noise noise noise" not in out


# ── AC4: budget trimming ─────────────────────────────────────────────────────

def test_budget_is_respected_with_truncation_notice():
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-001-Target.md",
                {"id": "STORY-001", "title": "Target"},
                "## Context\n\n" + "target words " * 60)
    write_doc(vault, "10_CONTEXT/BIG.md", "# Big\n\n" + "flock words " * 4000)
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "STORY-001", budget=1000)
    assert len(out.rstrip("\n")) <= 1000, f"budget exceeded: {len(out)}"
    assert "characters to satisfy budget" in out


def test_tiny_budget_degrades_without_crashing():
    _, vault = make_vault()
    write_issue(vault, "20_NEXT/STORY-001-Target.md",
                {"id": "STORY-001", "title": "Target"}, "## Context\n\nwords " * 200)
    write_doc(vault, "10_CONTEXT/BIG.md", "# Big\n\n" + "flock " * 2000)
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "STORY-001", budget=200)
    assert len(out.rstrip("\n")) <= 200


# ── AC9: existing vaults & layouts ───────────────────────────────────────────

def test_legacy_layout_cold_start():
    """A pre-existing legacy vault (no newvault tree) builds and queries fine."""
    vault = tempfile.mkdtemp(prefix="rvc-legacy-")
    os.makedirs(os.path.join(vault, "10_Issues", "01_To_Do"))
    with open(os.path.join(vault, ".rvc-root"), "w") as f:
        f.write("# RVC vault root\n")
    write_doc(vault, "10_Issues/01_To_Do/IDEA-001-Thing.md",
              "---\nid: IDEA-001\ntitle: Thing\n---\n\nflock notes\n")
    cache = rvc_cli.context_cache_update(vault)
    assert "IDEA-001" in cache["docs"]
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "IDEA-001")
    assert "# RVC Context Assembler: IDEA-001 (Thing)" in out


def test_notes_without_frontmatter_use_basename_identity():
    """Notes (`ROUTING`, `COMMANDS`) have an identity too — no id: needed."""
    _, vault = make_vault()
    write_doc(vault, "10_CONTEXT/ROUTING.md", "# RVC Vault — Routing\n\nrules flock\n")
    cache = rvc_cli.context_cache_update(vault)
    assert "ROUTING" in cache["docs"]
    _, out = capture_stdout(rvc_cli.cmd_context, vault, "ROUTING")
    assert out.startswith("# RVC Context Assembler: ROUTING")
    assert "rules flock" in out


# ── AC6: MCP daemon surface ──────────────────────────────────────────────────

def test_mcp_get_context_signature_exposes_semantic_controls():
    """rvcd.rvc_get_context accepts top_k, budget_chars, include_semantic."""
    tree = ast.parse((REPO_ROOT / "rvcd.py").read_text())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "rvc_get_context"), None)
    assert fn is not None, "rvcd.py: rvc_get_context not found"
    args = [a.arg for a in fn.args.args]
    assert args[:2] == ["project_path", "issue_id"]
    for name in ("top_k", "budget_chars", "include_semantic"):
        assert name in args, f"rvc_get_context missing '{name}'"
    defaults = [ast.literal_eval(d) for d in fn.args.defaults]
    assert defaults == [3, 40000, True], defaults
