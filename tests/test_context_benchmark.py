#!/usr/bin/env python3
"""STORY-033 quality target: recall@5 >= 80% on the hand-labeled benchmark.

Runs the real `rvc-vault` through the real ranker (the vault is copied to a
scratch dir first — RVC tests never write into a live vault). Ground-truth
documents that no longer exist are skipped; if too few survive, the test fails
loudly instead of grading an empty suite.

Also pins the story's performance targets with generous CI headroom:
cold index < 3000 ms (target 300 ms), warm update < 500 ms, query < 300 ms
(target 30 ms).
"""

import os
import pathlib
import shutil
import tempfile
import time

import helpers
from helpers import REPO_ROOT, rvc_cli

LIVE_VAULT = REPO_ROOT / "rvc-vault"
RECALL_TARGET = 0.80

# Hand-labeled ground truth from STORY-033 (Benchmark & Test Ground Truth).
BENCHMARK = {
    "STORY-031": ["10_CONTEXT/ROUTING.md", "10_CONTEXT/DECISIONS.md", "STORY-024"],
    "STORY-028": ["10_CONTEXT/DECISIONS.md", "10_CONTEXT/GOTCHAS.md", "STORY-029"],
    "STORY-029": ["10_CONTEXT/ROUTING.md", "10_CONTEXT/DECISIONS.md",
                  "10_CONTEXT/GOTCHAS.md"],
    "STORY-032": ["10_CONTEXT/specs/COMMANDS.md", "10_CONTEXT/specs/PROTOCOL.md"],
    "STORY-013": ["10_CONTEXT/DECISIONS.md", "10_CONTEXT/specs/PROTOCOL.md"],
}


def _copy_live_vault():
    root = tempfile.mkdtemp(prefix="rvc-bench-")
    vault = os.path.join(root, "vault")
    shutil.copytree(
        str(LIVE_VAULT), vault,
        ignore=shutil.ignore_patterns(
            ".obsidian", ".rvc-create.lock", rvc_cli.CONTEXT_CACHE_NAME))
    marker = rvc_cli.marker_file(str(LIVE_VAULT))
    if marker:
        # Carry the vault's effective config so the copy is self-contained:
        # since STORY-037 the marker lives at the project root, not in the
        # vault — a bare dir copy would otherwise fall back to LEGACY_TREE
        # and grade the ranker with the wrong bucket map.
        shutil.copy2(marker, os.path.join(vault, ".rvc-root"))
    return vault


def _expected_exists(vault, expected):
    if expected.endswith(".md"):
        return os.path.exists(os.path.join(vault, expected))
    return rvc_cli.find_file_by_id(vault, expected) is not None


def _found(paths, expected):
    return any(p == expected or p.endswith(expected + ".md") or expected in p
               for p in paths)


def test_benchmark_recall_at_5_and_quality_targets():
    vault = _copy_live_vault()
    tree = rvc_cli.resolve_tree(vault)

    t0 = time.perf_counter()
    cache = rvc_cli.context_cache_update(vault, force=True)
    cold_ms = (time.perf_counter() - t0) * 1000

    cases = expectations = hits = 0
    query_ms = 0.0
    for target_id, expected_docs in BENCHMARK.items():
        path = rvc_cli.find_file_by_id(vault, target_id)
        if not path:
            continue
        text = open(path, encoding="utf-8").read()
        rel = os.path.relpath(path, vault).replace(os.sep, "/")
        target_doc_id = rvc_cli._context_doc_id(rel, text)
        terms = rvc_cli._context_terms(text)
        t1 = time.perf_counter()
        ranked = rvc_cli.context_rank(cache, terms, top_k=5,
                                      exclude_ids={target_doc_id}, tree=tree)
        query_ms = max(query_ms, (time.perf_counter() - t1) * 1000)
        paths = [row[3] for row in ranked]
        cases += 1
        for expected in expected_docs:
            if not _expected_exists(vault, expected):
                continue
            expectations += 1
            hits += 1 if _found(paths, expected) else 0

    assert cases >= 4, f"benchmark too degraded: only {cases} targets found"
    assert expectations >= 8, f"benchmark too degraded: {expectations} ground-truth docs"
    recall = hits / expectations
    assert recall >= RECALL_TARGET, (
        f"recall@5 {recall:.0%} ({hits}/{expectations}) < {RECALL_TARGET:.0%}")

    t2 = time.perf_counter()
    rvc_cli.context_cache_update(vault)
    warm_ms = (time.perf_counter() - t2) * 1000

    assert cold_ms < 3000, f"cold index {cold_ms:.0f}ms is pathological (target 300ms)"
    assert warm_ms < 500, f"warm update {warm_ms:.0f}ms is pathological (target <2ms load)"
    assert query_ms < 300, f"query {query_ms:.0f}ms is pathological (target 30ms)"


def test_benchmark_ranks_are_deterministic():
    """Same vault, same query -> identical order (stable sorting)."""
    vault = _copy_live_vault()
    cache = rvc_cli.context_cache_update(vault, force=True)
    tree = rvc_cli.resolve_tree(vault)
    target = rvc_cli.find_file_by_id(vault, "STORY-029")
    text = open(target, encoding="utf-8").read()
    rel = os.path.relpath(target, vault).replace(os.sep, "/")
    terms = rvc_cli._context_terms(text)
    first = [row[3] for row in rvc_cli.context_rank(
        cache, terms, top_k=5, exclude_ids={rvc_cli._context_doc_id(rel, text)}, tree=tree)]
    second = [row[3] for row in rvc_cli.context_rank(
        cache, terms, top_k=5, exclude_ids={rvc_cli._context_doc_id(rel, text)}, tree=tree)]
    assert first == second
