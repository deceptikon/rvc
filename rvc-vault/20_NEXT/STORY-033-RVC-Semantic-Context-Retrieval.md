---
id: STORY-033
title: RVC Semantic Context Retrieval
type: story
priority: P1
created: 2026-09-16
domain: workflow_meta
domain_tags: ["retrieval", "context", "search", "cli"]
epic: "[[EPIC-001-RVC-Protocol]]"
aliases:
  - STORY-33
---

# STORY-033: RVC Semantic Context Retrieval

## Context
The legacy `rvc context <ID>` implementation relies entirely on resolving explicit `[[wikilinks]]` in the issue body, which has **proven completely useless in practice**:
1. **High maintenance & blind spots**: It demands manual link curation at authoring time. Crucial context—such as architectural rulings in `10_CONTEXT/DECISIONS.md`, traps in `10_CONTEXT/GOTCHAS.md`, or relevant sibling stories—is almost never explicitly linked, so agents operate blind to the real vault state.
2. **Uncontrolled noise dump**: When links *do* exist, it indiscriminately dumps the full text of every referenced file (STORY-012 measured 60–90K characters), overflowing LLM context windows with low-signal boilerplates.

**The Core Pivot**: Abandon manual wikilink resolution as the primary context engine. Instead, `rvc context <ID>` automatically extracts the semantic footprint of the issue (title, tags, headings, problem definition) and dynamically retrieves, ranks, and trims the most relevant knowledge from across the entire vault.

---

## Architectural Constraints & Invariants

1. **Zero-Dependency CLI Invariant (Mandatory Default)**:
   `rvc-cli.py` is a single-file, zero-dependency script running strictly on the Python standard library (`re`, `json`, `os`, `hashlib`, `math`, etc.).
   - The primary semantic/hybrid search baseline must be implemented in pure Python stdlib (e.g., BM25 / TF-IDF cosine similarity with tokenization, stopword filtering, frontmatter & Markdown header boosting).
   - It must run out of the box on fresh environments with no `pip install` steps required.
2. **Opt-in Vector Engines (Extension Tier)**:
   - Dense vector embeddings (e.g. `sqlite-vec`, `fastembed`, `sentence-transformers`, `chromadb`, or `qdrant-client`) must remain purely optional/pluggable extensions (e.g. via `rvcd.py` FastMCP daemon or an opt-in extra).
   - If an optional backend is unavailable or unconfigured, `rvc` must transparently fall back to the stdlib BM25 ranker with zero errors.
3. **Token & Character Budgeting (STORY-012 Intersection)**:
   - Prevent unbounded context dumps. Add `--budget <chars>` (default: 40,000 characters ~ 10,000 tokens).
   - Format includes target issue, hard references (explicit `[[wikilinks]]`), and soft references (semantic top-K).
   - When exceeding budget, lower-ranked items are truncated or summarized (frontmatter + title + headings + first 500 chars).
4. **Folder Drift & Document Identity Invariant**:
   - In RVC, issues continuously drift between folders (`00_INBOX` → `20_NEXT` → `30_ACTIVE` → `60_DONE`) via `git mv`.
   - The index decouples *identity* from *ephemeral folder paths*. The primary key in the index is the immutable **Document ID** (`id: STORY-033` or canonical base filename `ROUTING`), never the volatile path.
   - When an issue moves folders, its ID and content hash are identical; only the `rel_path` pointer updates, requiring zero re-tokenization or re-computation.
5. **When Indexing Occurs (Lifecycle Triggers)**:
   - **Lazy JIT on Query (`rvc context`)**: Performs an instantaneous `st_mtime` / size check (< 5 ms across 200+ docs). Only added, deleted, or altered files are incrementally re-indexed. If nothing changed, the cache loads in < 2 ms.
   - **Eager Mutation Hooks**: `rvc create` inserts the new issue into the index; `rvc issue <ID> <action>` updates the file path pointer on `git mv`; `rvc rescan` performs a full consistency reconciliation.
   - Cache file `.rvc-context-cache.json` is strictly vault-local and git-ignored.
6. **Existing Vault Compatibility & Auto Cold-Start**:
   - Compatible with existing vaults regardless of layout preset (`newvault` or `legacy`).
   - If `.rvc-context-cache.json` does not exist or fails to parse (corrupted), `rvc context` automatically triggers a zero-intervention cold-start build without crashing or requiring manual migration.
7. **Explicit Reindexing Support**:
   - Supports explicit force-rebuild via `rvc context <ID> --reindex` or as part of `rvc rescan`. Useful when files are manipulated externally via Obsidian or git branches.
8. **ID Normalization**:
   - Issue identification must support unpadded numerals (e.g. `STORY-33` matches `STORY-033`) across `find_file_by_id`, `rvc context`, and `rvc issue`.

---

## Proposed CLI & MCP Interface

### CLI: `rvc context`
```bash
rvc context <ID> [--top-k N] [--budget CHARS] [--mode full|summary] [--no-semantic] [--reindex]
```
- `<ID>`: Target issue or note (with unpadded alias support).
- `--top-k N`: Number of semantic/related documents to retrieve (default: `3`).
- `--budget CHARS`: Maximum character budget for the total output (default: `40000`).
- `--mode full|summary`: `full` includes complete text within budget; `summary` extracts frontmatter, goal, and acceptance criteria.
- `--no-semantic`: Retain legacy behavior (only resolve explicit `[[wikilinks]]`).
- `--reindex`: Force a full rebuild of `.rvc-context-cache.json` before querying.

### MCP Daemon: `rvcd.py`
```python
@mcp.tool()
def rvc_get_context(
    project_path: str,
    issue_id: str,
    top_k: int = 3,
    budget_chars: int = 40000,
    include_semantic: bool = True
) -> dict:
    ...
```

### Context Output Structure
```markdown
# RVC Context Assembler: STORY-033 (RVC Semantic Context Retrieval)

## 1. Target Issue
[Target issue frontmatter and body]

## 2. Explicit References (Hard Signals)
--- REFERENCE: [[EPIC-001-RVC-Protocol]] ---
File: 20_NEXT/EPIC-001-RVC-Protocol.md
[Reference content...]
--- END OF REFERENCE ---

## 3. Discovered Related Context (Soft Signals — Top-K Semantic/BM25)
--- RELATED: [[10_CONTEXT/DECISIONS.md]] (Relevance Score: 0.76) ---
Matched terms: flock, zero-dependency, concurrency, STORY-013
[Relevant excerpt or summary...]
--- END OF RELATED ---

--- RELATED: [[10_CONTEXT/specs/PROTOCOL.md]] (Relevance Score: 0.62) ---
[Relevant excerpt or summary...]
--- END OF RELATED ---
```

---

## Research Questions & Survey Matrix

Evaluate vector & lexical approaches on a 100–1000 document technical markdown vault:

| Candidate | Runtime Dependency | Offline Capable | Index Size | Cold Index Time (200 docs) | Query Latency | Notes / Fit for RVC |
|---|---|---|---|---|---|---|
| **Stdlib BM25 / TF-IDF** | None (Python stdlib) | Yes (100%) | < 500 KB | < 200 ms | < 10 ms | Mandatory default; zero install |
| **sqlite-vec** | `sqlite3` + extension | Yes | ~5-10 MB | 1-3 s | < 5 ms | Clean SQLite integration, requires binary extension |
| **FastEmbed / ONNX** | `fastembed` (~150MB) | Yes (cached model) | ~10-50 MB | 2-5 s | 20-50 ms | Embedded local ONNX runtime |
| **ChromaDB / Qdrant** | Heavy pip packages | Yes (embedded mode)| ~50-100 MB | 3-8 s | 20-60 ms | Too heavy for single-file zero-dependency CLI |

---

## Acceptance Criteria

- [ ] **AC 1: Zero-Dependency Stdlib Retrieval Engine**
  - Implement a pure Python standard library BM25/TF-IDF relevance engine in `rvc-cli.py`.
  - Tokenization accounts for kebab-case identifiers (`STORY-013`), code snippets, frontmatter tags, and Markdown headings (headings get 2x weight boost; title/id gets 3x boost).
- [ ] **AC 2: Incremental Index Caching, Drift Resilience & Git Hygiene**
  - Cache inverted index & document metadata in `.rvc-context-cache.json` at vault root, keyed by immutable Document ID (`STORY-XXX` or spec name) rather than volatile folder path.
  - On folder transitions (`git mv`), location pointers update with zero re-tokenization.
  - Cache respects `st_mtime` and content hashes; re-indexes only modified files.
  - Add `.rvc-context-cache.json` to `VAULT_GITIGNORE_LINES` in `rvc-cli.py` (`_write_vault_gitignore`) and root `.gitignore`, ensuring the cache is never tracked.
- [ ] **AC 3: Hybrid Retrieval & Context Assembly**
  - `rvc context <ID>` outputs:
    1. The target issue itself.
    2. Explicit `[[wikilinks]]` references (deduplicated).
    3. Top-K related documents discovered by relevance score (excluding target and already-linked files).
  - Flags supported: `--top-k <N>` (default 3), `--budget <chars>` (default 40000), `--no-semantic`, `--reindex`.
- [ ] **AC 4: Token / Character Budget Trimming**
  - Respect character budget; if output exceeds budget, truncate low-priority / soft references first with clear truncation notices (`... [truncated N characters to satisfy budget] ...`).
- [ ] **AC 5: ID Normalization for Context & Issue Commands**
  - `find_file_by_id` and `rvc context` support unpadded numbers (e.g. `STORY-33` matches `STORY-033`).
- [ ] **AC 6: MCP Daemon Integration (`rvcd.py`)**
  - `rvc_get_context` accepts `top_k`, `budget_chars`, and `include_semantic` parameters and returns the structured context payload.
- [ ] **AC 7: Architectural Decision Recorded**
  - Record chosen search architecture, caching strategy, and dependency policy in `10_CONTEXT/DECISIONS.md`.
- [ ] **AC 8: Zero Hard Dependency Verification**
  - Standalone `rvc-cli.py` runs without any pip-installed dependencies. Local test suite passes with stdlib only.
- [ ] **AC 9: Existing Vaults & Explicit Reindexing Support**
  - Automatic cold-start index build for pre-existing vaults (both `newvault` and `legacy` layouts) upon first run.
  - Reindex flag: `rvc context <ID> --reindex` forces full rebuild.
  - Automatic recovery: if `.rvc-context-cache.json` is missing or corrupted, transparently re-indexes without failure.
- [ ] **AC 10: Help System & Specification Synchronization**
  - Update `10_CONTEXT/specs/COMMANDS.md` with the new `rvc context` signature, flags, and defaults.
  - Update `rvc help` and `rvc help context` text in `rvc-cli.py` to match `COMMANDS.md` verbatim per the STORY-032 help contract.

---

## Benchmark & Test Ground Truth

Evaluate recall@5 on a hand-labeled benchmark suite of 5 actual issues from `rvc-vault`:

1. **STORY-031** (`rvc plate drops 40_DECIDE stories`):
   - Ground Truth Expected: `10_CONTEXT/ROUTING.md`, `10_CONTEXT/DECISIONS.md`, `STORY-024`.
2. **STORY-028** (`rvc create mints no id field`):
   - Ground Truth Expected: `10_CONTEXT/DECISIONS.md`, `10_CONTEXT/GOTCHAS.md`, `STORY-029`.
3. **STORY-029** (`This vault violates its own constitution`):
   - Ground Truth Expected: `10_CONTEXT/ROUTING.md`, `10_CONTEXT/DECISIONS.md`, `10_CONTEXT/GOTCHAS.md`.
4. **STORY-032** (`rvc help: nested command reference with exact descriptions`):
   - Ground Truth Expected: `10_CONTEXT/specs/COMMANDS.md`, `10_CONTEXT/specs/PROTOCOL.md`.
5. **STORY-013** (`RVC CLI Security & Performance Hardening`):
   - Ground Truth Expected: `10_CONTEXT/DECISIONS.md`, `10_CONTEXT/specs/PROTOCOL.md`.

**Quality Targets:**
- Recall@5 >= 80% across the benchmark suite.
- Cold cache index build time < 300 ms on ~200 vault files.
- Warm query latency < 30 ms.

---

## Definition of Done

- `STORY-033-RVC-Semantic-Context-Retrieval.md` verified and free of constitutional violations (`rvc doctor` passes).
- Architecture decision recorded in `10_CONTEXT/DECISIONS.md`.
- `rvc context <ID>` delivers both hard wikilinks and scored semantic suggestions within specified budget.
- `rvc help` and `rvc help context` updated and consistent with `10_CONTEXT/specs/COMMANDS.md`.
- `.rvc-context-cache.json` covered in `VAULT_GITIGNORE_LINES` and verified in `tests/test_init_gitignore.py`.
- Unit tests added to `tests/test_context_semantic.py` verifying BM25 scoring, cache freshness, budgeting, and ID alias lookup (`STORY-33` -> `STORY-033`).
- Local test runner `python3 tests/run_tests.py` passes 100% cleanly without external dependencies.

---

## Related
- [[STORY-012]] — Context token optimization & truncation budget.
- [[STORY-013]] — Security, `.rvc-index.json` ID map, lock-safety.
- [[STORY-019]] — RVC-Link node in conductor pipeline.
- [[STORY-032]] — Command reference and `COMMANDS.md` specification.
