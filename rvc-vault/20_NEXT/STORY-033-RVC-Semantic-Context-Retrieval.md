---
id: STORY-033
title: RVC Semantic Context Retrieval
type: story
priority: P1
started: 2026-09-16
---

# STORY-033: RVC Semantic Context Retrieval

## Context
`rvc context <ID>` today only resolves explicit [[wikilinks]] from the issue body and prints the full text of each referenced file (STORY-012 measured 60-90K chars). It cannot surface relevant vault docs the issue does not explicitly link — the decision record, sibling spec, or prior story that actually bears on the work. As the vault grows (10_CONTEXT/specs/, 90_ARCHIVE/, cross-vault EPICs) the noise floor rises and the signal drops.

Goal: `rvc context <ID>` retrieves *related* context — ranked, trimmed, grounded in semantic similarity to the issue — instead of a bulk dump of everything the issue happens to link.

## Research Questions
- What embedding/index approach fits a local-first, git-backed vault of markdown files? Survey: ChromaDB, Qdrant (embedded client mode), LanceDB, sqlite-vec, FAISS — plus a zero-dependency baseline (BM25 / TF-IDF cosine) for comparison.
- Which embedding model? Small local (sentence-transformers / onnx) vs API — offline requirement, cache size, quality on short technical markdown.
- Where does the index live and how is it kept fresh? `.rvc-index.json` (STORY-013) overlap; incremental reindex on create/transition vs full rebuild; git-ignore policy.
- How does semantic recall combine with explicit wikilinks? (wikilinks = hard signal, always included; semantic top-K = soft signal, scored + trimmed by token budget per STORY-012.)

## Acceptance Criteria
- [ ] Survey report comparing >= 4 candidates (ChromaDB, Qdrant, one embedded/vector option, and the zero-dep baseline) on: dependency weight, offline support, index size, incremental-update story, query latency at vault scale (100-1000 docs).
- [ ] Decision recorded in 10_CONTEXT/DECISIONS.md: chosen engine + embedding model + index storage/git-ignore policy + rebuild strategy.
- [ ] PoC spike: index the rvc-vault itself; `rvc context STORY-XXX` (prototype) returns top-K related docs ranked with a score, alongside the existing wikilinked set.
- [ ] Recommendation for the `rvc context` interface: `--top-k`, relevance score display, per-file trimming to stay under a token budget (ties into STORY-012).
- [ ] No new hard runtime dependencies added to the CLI without an explicit decision (stdlib-only suite today; the chosen engine may be optional/opt-in).

## Test Case Requirements
- PoC evaluates recall@K on a hand-labeled mini-set (e.g. 5 issues whose *related* docs are known a priori) rather than only wikilinked ones.
- Benchmark: time to build the index and time per query on the current rvc-vault (~200 md files).

## Related
- [[STORY-012]] — context token optimization; this story's trimming budget intersects it.
- [[STORY-013]] — `.rvc-index.json` id->file map; the semantic index may extend or reuse it.
- [[STORY-019]] — RVC-Link; existing link-resolution machinery.
