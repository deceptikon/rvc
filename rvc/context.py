"""Semantic BM25 context engine and retrieval."""

import os
import sys
import re
import json
import math
import hashlib

from rvc.core import resolve_tree, tree_dirs, find_file_by_id, build_vault_index, _find_in_index
from rvc.plate import plate_frontmatter

CONTEXT_CACHE_NAME = ".rvc-context-cache.json"
CONTEXT_CACHE_VERSION = 1
CONTEXT_DEFAULT_TOP_K = 3
CONTEXT_DEFAULT_BUDGET = 12000
CONTEXT_BM25_K1 = 1.5
# b=1.0 is full length normalization: a long debate transcript must not outrank
# a short reference by accumulating weak matches. Measured on the STORY-033
# benchmark: recall@5 77% at b=0.75 (okapi default) vs 92% at b=1.0.
CONTEXT_BM25_B = 1.0
CONTEXT_SUMMARY_CHARS = 500
CONTEXT_MATCH_LIMIT = 6
CONTEXT_KNOWLEDGE_ROOT_BOOST = 1.5
CONTEXT_KNOWLEDGE_SUBDIR_BOOST = 1.2

CONTEXT_TRUNCATED_FMT = "... [truncated {n} characters to satisfy budget] ..."
CONTEXT_OMITTED_FMT = "... [omitted {n} characters to satisfy budget] ..."

CONTEXT_STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have
he her his how i if in into is it its may might more most must no nor not of
on or our out over own said she should so some such than that the their them
then there these they this those to too under until up upon us use used using
was we were what when where which while who whom why will with would you your
""".split())

CONTEXT_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*")
CONTEXT_H1_RE = re.compile(r"^#\s+(.*)$")
CONTEXT_H2_RE = re.compile(r"^#{2,6}\s+(.*)$")
CONTEXT_FENCE_RE = re.compile(r"^\s*```")
CONTEXT_TITLE_KEYS = frozenset(("title", "id", "aliases"))
CONTEXT_TAG_KEYS = frozenset(("tags", "domain_tags", "keywords"))


def _context_canon(token):
    """Canonical token form: `STORY-013` and `STORY-13` become `story-13`."""
    parts = re.split(r"([-_.])", token)
    for i, part in enumerate(parts):
        if i % 2 == 0 and part.isdigit() and len(part) > 1:
            parts[i] = part.lstrip("0") or "0"
    return "".join(parts)


def _context_emit(weights, text, weight, surfaces=None):
    """Accumulate weighted terms from `text`; kebab ids also emit their parts."""
    for match in CONTEXT_TOKEN_RE.finditer(text):
        raw = match.group(0)
        token = _context_canon(raw.lower())
        if len(token) >= 2 and token not in CONTEXT_STOPWORDS:
            weights[token] = weights.get(token, 0.0) + weight
            if surfaces is not None and token not in surfaces:
                surfaces[token] = raw
        for part in re.split(r"[-_.]", raw):
            sub = _context_canon(part.lower())
            if sub == token or len(sub) < 2 or sub in CONTEXT_STOPWORDS:
                continue
            weights[sub] = weights.get(sub, 0.0) + weight * 0.5
            if surfaces is not None and sub not in surfaces:
                surfaces[sub] = part


def _context_chunk_terms(chunk, surfaces=None):
    """Weighted terms for one section: title/id 3x, tags 2.5x, headings 2x."""
    weights = {}
    lines = chunk.splitlines()
    i = 0
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", lines[i])
            if m:
                key = m.group(1).lower()
                if key in CONTEXT_TITLE_KEYS:
                    _context_emit(weights, m.group(2), 3.0, surfaces)
                elif key in CONTEXT_TAG_KEYS:
                    _context_emit(weights, m.group(2), 2.5, surfaces)
                else:
                    _context_emit(weights, m.group(2), 1.5, surfaces)
            i += 1
        i += 1
    in_fence = False
    for line in lines[i:]:
        if CONTEXT_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            _context_emit(weights, line, 1.0, surfaces)
            continue
        m1 = CONTEXT_H1_RE.match(line)
        if m1:
            _context_emit(weights, m1.group(1), 3.0, surfaces)
            continue
        m2 = CONTEXT_H2_RE.match(line)
        if m2:
            _context_emit(weights, m2.group(1), 2.0, surfaces)
            continue
        _context_emit(weights, line, 1.0, surfaces)
    return weights


def _context_chunks(text):
    """Split a doc into citable chunks: frontmatter, then one chunk per heading."""
    chunks, current, in_fence = [], [], False
    for line in text.splitlines():
        if CONTEXT_FENCE_RE.match(line):
            in_fence = not in_fence
        if not in_fence and (CONTEXT_H1_RE.match(line) or CONTEXT_H2_RE.match(line)) and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))
    return [c for c in chunks if c.strip()]


def _context_terms(text, surfaces=None):
    """Weighted term footprint of a document (merge of its chunks)."""
    merged = {}
    for chunk in _context_chunks(text):
        for token, weight in _context_chunk_terms(chunk, surfaces=surfaces).items():
            merged[token] = merged.get(token, 0.0) + weight
    return merged


def _context_split_frontmatter(text):
    """(raw frontmatter incl. fences, body) — (None, text) when absent."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    return text[:end + 4], text[end + 4:]


def _context_summary(text):
    """Frontmatter + title + heading outline + first 500 chars (AC4 trim form)."""
    raw, body = _context_split_frontmatter(text)
    headings = re.findall(r"(?m)^#{1,6}\s+.*$", body)
    stripped = re.sub(r"(?m)^#{1,6}\s+.*$", "", body).strip()
    parts = [raw] if raw else []
    parts.extend(headings)
    if stripped:
        parts.append(stripped[:CONTEXT_SUMMARY_CHARS])
    return "\n".join(parts)


def _context_goal_summary(text):
    """Frontmatter + goal/problem/acceptance sections (for --mode summary)."""
    raw, body = _context_split_frontmatter(text)
    sections = re.split(r"(?m)^(##\s+.*)$", body)
    kept = []
    for i in range(1, len(sections), 2):
        heading = sections[i]
        content = sections[i + 1] if i + 1 < len(sections) else ""
        if re.search(r"goal|acceptance|problem|context|summary|objective|why",
                     heading, re.I):
            kept.append((heading + content).strip())
    if not kept:
        return _context_summary(text)
    parts = [raw] if raw else []
    parts.append("\n\n".join(kept))
    return "\n".join(parts)


def _context_target_summary(rel_path, text):
    """Clean high-density target issue summary: metadata + Why/Problem + Acceptance Criteria."""
    raw, body = _context_split_frontmatter(text)
    fields = plate_frontmatter(text)
    state = rel_path.split("/")[0] if "/" in rel_path else "root"
    priority = fields.get("priority", "None")
    itype = fields.get("type", "issue")

    header_lines = [
        f"- **State:** `{state}` | **Priority:** `{priority}` | **Type:** `{itype}` | **File:** `{rel_path}`"
    ]

    sections = re.split(r"(?m)^(#{1,6}\s+.*)$", body)
    kept = []
    for i in range(1, len(sections), 2):
        heading = sections[i]
        content = sections[i + 1] if i + 1 < len(sections) else ""
        if re.search(r"why|problem|goal|objective|context|acceptance", heading, re.I):
            clean_c = content.strip()
            if len(clean_c) > 1200:
                clean_c = clean_c[:1200].rsplit(" ", 1)[0] + " ...\n*(research/details omitted for brevity)*"
            kept.append(f"{heading.strip()}\n{clean_c}")

    if not kept:
        body_snippet = body.strip()[:600]
        kept.append(body_snippet)

    return "\n".join(header_lines) + "\n\n" + "\n\n".join(kept)


def _context_hard_summary(spec_text, max_chars=350):
    """One-line title/meta plus ~300-char excerpt of goal/why section."""
    raw, body = _context_split_frontmatter(spec_text)
    fields = plate_frontmatter(spec_text)
    title = fields.get("title") or _context_doc_title(spec_text, "")
    sections = re.split(r"(?m)^(#{1,6}\s+.*)$", body)
    core = []
    for i in range(1, len(sections), 2):
        heading = sections[i]
        content = sections[i + 1] if i + 1 < len(sections) else ""
        if re.search(r"goal|problem|why|objective|summary", heading, re.I):
            clean = content.strip()
            if clean:
                core.append(clean)
                break
    if not core:
        paras = [p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        core = paras[:1]
    snippet = core[0] if core else body.strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rsplit(" ", 1)[0] + " ..."
    snippet = re.sub(r"\n{2,}", "\n", snippet)
    return title, snippet


def _context_extract_excerpt(text, best_ci=None, matched_terms=None, max_chars=350):
    """Extract a focused snippet around the best-matching chunk or terms."""
    chunks = _context_chunks(text)
    chunk = ""
    if best_ci is not None and 0 <= best_ci < len(chunks):
        if best_ci == 0 and chunks[0].strip().startswith("---") and len(chunks) > 1:
            chunk = chunks[1]
        else:
            chunk = chunks[best_ci]
    elif len(chunks) > 1 and chunks[0].strip().startswith("---"):
        chunk = chunks[1]
    elif chunks:
        chunk = chunks[0]
    else:
        chunk = text

    lines = chunk.strip().splitlines()
    heading = ""
    body_lines = lines
    if lines and re.match(r"^#{1,6}\s+", lines[0]):
        heading = lines[0].strip()
        body_lines = lines[1:]
    body = "\n".join(body_lines).strip()
    if not body:
        body = text.strip()

    best_pos = -1
    if matched_terms:
        for t in matched_terms:
            pos = body.lower().find(t.lower())
            if pos != -1:
                best_pos = pos
                break

    if len(body) <= max_chars:
        excerpt = body
    elif best_pos != -1:
        start = max(0, best_pos - 60)
        end = min(len(body), start + max_chars)
        if start > 0:
            sp = body.find(" ", start)
            if sp != -1 and sp < start + 25:
                start = sp + 1
        if end < len(body):
            sp = body.rfind(" ", start, end)
            if sp != -1 and sp > end - 25:
                end = sp
        prefix = "... " if start > 0 else ""
        suffix = " ..." if end < len(body) else ""
        excerpt = prefix + body[start:end].strip() + suffix
    else:
        excerpt = body[:max_chars].rsplit(" ", 1)[0] + " ..."

    excerpt = re.sub(r"\n{2,}", "\n", excerpt)
    return heading, excerpt


def _context_doc_id(rel_path, text):
    """Immutable Document ID: frontmatter `id:` else the filename's id shape."""
    fields = plate_frontmatter(text)
    doc_id = fields.get("id")
    if doc_id:
        return doc_id
    base = os.path.basename(rel_path)
    if base.endswith(".md"):
        base = base[:-3]
    m = re.match(r"^([A-Za-z]+-\d+)", base)
    return m.group(1) if m else base


def _context_doc_title(text, rel_path):
    """Human title: frontmatter `title:` else the first H1 else the filename."""
    fields = plate_frontmatter(text)
    if fields.get("title"):
        return fields["title"].strip().strip("\"'")
    m = re.search(r"(?m)^#\s+(.*)$", text)
    if m:
        return m.group(1).strip()
    return os.path.basename(rel_path)


def context_cache_path(vault_path):
    return os.path.join(vault_path, CONTEXT_CACHE_NAME)


def _context_hash(text):
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def _context_read(vault_path, rel_path):
    try:
        with open(os.path.join(vault_path, rel_path), "r",
                  encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _context_scan(vault_path):
    """{rel_path: (mtime, size)} for every .md file (hidden dirs skipped)."""
    found = {}
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            found[os.path.relpath(path, vault_path).replace(os.sep, "/")] = (
                st.st_mtime, st.st_size)
    return found


def _context_empty_cache():
    return {"version": CONTEXT_CACHE_VERSION, "docs": {}, "postings": {},
            "chunk_count": 0, "chunk_total_len": 0.0}


def _context_load_cache(vault_path):
    """Load the cache; None when missing, unreadable, or structurally invalid."""
    try:
        with open(context_cache_path(vault_path), "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(cache, dict) or cache.get("version") != CONTEXT_CACHE_VERSION:
        return None
    if not isinstance(cache.get("docs"), dict) or not isinstance(cache.get("postings"), dict):
        return None
    if not isinstance(cache.get("chunk_count"), int):
        return None
    if not isinstance(cache.get("chunk_total_len"), (int, float)):
        return None
    for meta in cache["docs"].values():
        if not isinstance(meta, dict) or "path" not in meta or "chunk_lens" not in meta:
            return None
    return cache


def _context_save_cache(vault_path, cache):
    """Atomic best-effort write — a torn cache never replaces a good one."""
    path = context_cache_path(vault_path)
    tmp = f"{path}.tmp{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, separators=(",", ":"), ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _context_doc_key(cache, doc_id, rel_path):
    """Ensure duplicate IDs across different files (e.g. archive/superseded) don't collide."""
    if doc_id not in cache["docs"] or cache["docs"][doc_id].get("path") == rel_path:
        return doc_id
    return f"{doc_id}::{rel_path}"


def _context_index_doc(cache, vault_path, rel_path, text, mtime, size):
    """(Re)tokenize one document into the cache; returns its Document ID/key."""
    doc_id = _context_doc_id(rel_path, text)
    doc_key = _context_doc_key(cache, doc_id, rel_path)
    if doc_key in cache["docs"]:
        _context_remove_doc(cache, doc_key)
    chunks = _context_chunks(text)
    chunk_lens = []
    for ci, chunk in enumerate(chunks):
        terms = _context_chunk_terms(chunk)
        chunk_lens.append(sum(terms.values()))
        for token, weight in terms.items():
            cache["postings"].setdefault(token, {}).setdefault(doc_key, []).append(
                [ci, round(weight, 4)])
    cache["docs"][doc_key] = {
        "id": doc_id,
        "path": rel_path,
        "mtime": mtime,
        "size": size,
        "hash": _context_hash(text),
        "chunks": len(chunks),
        "chunk_lens": chunk_lens,
    }
    cache["chunk_count"] += len(chunks)
    cache["chunk_total_len"] += sum(chunk_lens)
    return doc_key


def _context_remove_doc(cache, doc_key):
    meta = cache["docs"].pop(doc_key, None)
    if meta is None:
        return
    cache["chunk_count"] = max(0, cache["chunk_count"] - meta.get("chunks", 0))
    cache["chunk_total_len"] = max(
        0.0, cache["chunk_total_len"] - sum(meta.get("chunk_lens", [])))
    for token in list(cache["postings"].keys()):
        postings = cache["postings"][token]
        if doc_key in postings:
            del postings[doc_key]
            if not postings:
                del cache["postings"][token]


def context_cache_update(vault_path, force=False):
    """Bring `.rvc-context-cache.json` up to date; returns the cache dict.

    Incremental by design: only added/altered/deleted files are touched. A file
    whose stat matches a vanished path is the same document moved — it repaths
    with zero re-tokenization. A corrupt cache cold-starts transparently.
    """
    cache = None if force else _context_load_cache(vault_path)
    scanned = _context_scan(vault_path)
    if cache is None:
        cache = _context_empty_cache()
        by_path = {}
        dirty = True
    else:
        by_path = {meta["path"]: doc_key for doc_key, meta in cache["docs"].items()}
        dirty = False

    # 1. Repath first: an added path whose stat matches a vanished doc is a move.
    vanished = [doc_key for doc_key, meta in cache["docs"].items()
                if meta["path"] not in scanned]
    added = [path for path in scanned if path not in by_path]
    for path in list(added):
        mtime, size = scanned[path]
        for doc_key in list(vanished):
            meta = cache["docs"][doc_key]
            if meta["size"] == size and abs(meta["mtime"] - mtime) < 1e-4:
                meta["path"] = path
                meta["mtime"], meta["size"] = mtime, size
                by_path[path] = doc_key
                added.remove(path)
                vanished.remove(doc_key)
                dirty = True
                break

    # 2. Deletions.
    for doc_key in vanished:
        _context_remove_doc(cache, doc_key)
        dirty = True

    # 3. Additions and modifications.
    for rel_path, (mtime, size) in scanned.items():
        if rel_path in added:
            text = _context_read(vault_path, rel_path)
            if text is None:
                continue
            _context_index_doc(cache, vault_path, rel_path, text, mtime, size)
            dirty = True
            continue
        doc_key = by_path.get(rel_path)
        if doc_key is None or doc_key not in cache["docs"]:
            continue
        meta = cache["docs"][doc_key]
        if meta["mtime"] == mtime and meta["size"] == size:
            continue
        text = _context_read(vault_path, rel_path)
        if text is None:
            continue
        if _context_hash(text) == meta["hash"]:
            meta["mtime"], meta["size"] = mtime, size
            dirty = True
            continue
        old_key = doc_key
        new_key = _context_index_doc(cache, vault_path, rel_path, text, mtime, size)
        if new_key != old_key and old_key in cache["docs"]:
            _context_remove_doc(cache, old_key)
        dirty = True

    if dirty:
        _context_save_cache(vault_path, cache)
    return cache


def context_cache_repath(vault_path, old_path, new_path):
    """Update a document's path pointer after a move — no re-tokenization."""
    cache = _context_load_cache(vault_path)
    if cache is None:
        return
    old_rel = os.path.relpath(old_path, vault_path).replace(os.sep, "/")
    new_rel = os.path.relpath(new_path, vault_path).replace(os.sep, "/")
    for meta in cache["docs"].values():
        if meta.get("path") == old_rel:
            meta["path"] = new_rel
            try:
                st = os.stat(new_path)
                meta["mtime"], meta["size"] = st.st_mtime, st.st_size
            except OSError:
                pass
            _context_save_cache(vault_path, cache)
            return


def _context_archive_dirs(tree):
    """Buckets whose docs are never soft suggestions (indexed, not offered)."""
    dirs = [tree[v].rstrip("/") for v in ("evict", "supersede")
            if tree and tree.get(v)]
    return tuple(dirs) if dirs else ("90_ARCHIVE",)


def _context_is_archived(rel_path, archive_dirs):
    return any(rel_path == d or rel_path.startswith(d + "/") for d in archive_dirs)


def _context_knowledge_prior(rel_path, tree):
    """Prior for docs under the vault's knowledge root (root > nested)."""
    root = (tree or {}).get("roadmap")
    if not root:
        return 1.0
    root = root.rstrip("/")
    if rel_path == root or rel_path.startswith(root + "/"):
        rest = rel_path[len(root):].lstrip("/")
        return CONTEXT_KNOWLEDGE_SUBDIR_BOOST if "/" in rest else CONTEXT_KNOWLEDGE_ROOT_BOOST
    return 1.0


def context_rank(cache, term_weights, surfaces=None, top_k=CONTEXT_DEFAULT_TOP_K,
                 exclude_ids=(), exclude_paths=(), tree=None):
    """Rank docs against a weighted term footprint; returns top scoring entries.

    Each entry is `(doc_id, score, matched_surfaces, rel_path)`, best first.
    A document's score is its best matching section (chunk-level BM25).
    """
    docs = cache.get("docs") or {}
    postings = cache.get("postings") or {}
    n_docs = len(docs)
    if not n_docs or not term_weights:
        return []
    exclude_ids = set(exclude_ids)
    exclude_paths = set(exclude_paths)
    archive_dirs = _context_archive_dirs(tree)
    chunk_total = cache.get("chunk_total_len", 0.0)
    chunk_count = cache.get("chunk_count", 0)
    chunk_avg = (chunk_total / chunk_count) if chunk_count else 1.0
    if chunk_avg <= 0:
        chunk_avg = 1.0

    chunk_scores = {}
    for token, qw in term_weights.items():
        postings_for_term = postings.get(token)
        if not postings_for_term:
            continue
        df = len(postings_for_term)
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        for doc_id, entries in postings_for_term.items():
            if doc_id in exclude_ids:
                continue
            meta = docs.get(doc_id)
            if meta is None:
                continue
            scores = chunk_scores.setdefault(doc_id, {})
            chunk_lens = meta.get("chunk_lens", [])
            for ci, weight in entries:
                clen = chunk_lens[ci] if ci < len(chunk_lens) else 1.0
                denom = weight + CONTEXT_BM25_K1 * (
                    1 - CONTEXT_BM25_B + CONTEXT_BM25_B * (clen / chunk_avg))
                scores[ci] = scores.get(ci, 0.0) + (
                    qw * idf * weight * (CONTEXT_BM25_K1 + 1) / denom)

    ranked = []
    for doc_id, scores in chunk_scores.items():
        meta = docs[doc_id]
        rel_path = meta["path"]
        if rel_path in exclude_paths or _context_is_archived(rel_path, archive_dirs):
            continue
        best_ci = max(scores, key=lambda ci: (scores[ci], -ci))
        score = scores[best_ci] * _context_knowledge_prior(rel_path, tree)
        ranked.append((score, doc_id, best_ci, rel_path))
    ranked.sort(key=lambda row: (-row[0], row[3]))

    results = []
    for score, doc_id, best_ci, rel_path in ranked[:top_k]:
        contributions = []
        for token, qw in term_weights.items():
            entries = postings.get(token, {}).get(doc_id)
            if not entries:
                continue
            for ci, weight in entries:
                if ci == best_ci:
                    contributions.append((qw * weight, token))
                    break
        contributions.sort(key=lambda row: (-row[0], row[1]))
        matched = [((surfaces or {}).get(token, token))
                   for _, token in contributions[:CONTEXT_MATCH_LIMIT]]
        results.append((doc_id, score, matched, rel_path, best_ci))
    return results


def _context_block_body(block):
    form = block["form"]
    if form == "gone":
        return ""
    if form == "stub":
        return block.get("stub", "")
    if form == "full":
        return block["text"]
    if form == "summary":
        return block["summary"]
    if form == "trunc":
        limit = max(0, block.get("limit", 0))
        removed = max(0, len(block["text"]) - limit)
        return block["text"][:limit] + "\n" + CONTEXT_TRUNCATED_FMT.format(n=removed)
    return CONTEXT_OMITTED_FMT.format(n=len(block["text"]))


def _context_block_text(block, mode="summary"):
    if block["form"] == "gone":
        return ""
    if block["form"] == "stub":
        return block.get("stub", "")
    if mode == "summary" and block["form"] == "summary":
        if block.get("kind") == "hard":
            title_meta = f" (*{block['title']}*)" if block.get("title") else ""
            summary = block["summary"].strip()
            summary_indented = "\n  > ".join(summary.splitlines())
            return f"- [[{block['link']}]]{title_meta}\n  > {summary_indented}"
        if block.get("kind") == "soft":
            terms_line = f"\n  Matched terms: {block.get('terms_str', '')}" if block.get("terms_str") else ""
            sec = f"> **Section:** `{block['section']}`\n  " if block.get("section") else ""
            summary = block["summary"].strip()
            summary_indented = "\n  > ".join(summary.splitlines())
            return f"- [[{block['path']}]] (Relevance Score: {block['score']:.2f}){terms_line}\n  {sec}> {summary_indented}"
    parts = [block["header"]]
    parts.extend(block.get("meta", ()))
    body = _context_block_body(block)
    if body:
        parts.append(body)
    if block.get("footer"):
        parts.append(block["footer"])
    return "\n".join(parts)


def _context_assemble(target_id, target_title, target, hard_blocks, missing,
                      soft_blocks, budget, mode):
    """Render the context payload, degrading lowest-priority blocks first.

    Priority is target > hard refs > soft refs; within a tier the last item
    degrades first. Forms: full -> summary -> truncated -> omitted -> stub
    (one-line notice) -> gone.
    """
    if mode == "summary":
        for block in [target] + hard_blocks + soft_blocks:
            block["form"] = "summary"
    order = list(reversed(soft_blocks)) + list(reversed(hard_blocks)) + [target]

    def render():
        header = f"# RVC Context Assembler: {target_id}"
        if target_title:
            header += f" ({target_title})"
        parts = [header, "", "## 1. Target Issue", _context_block_body(target)]
        visible_hard = [b for b in hard_blocks if b["form"] != "gone"]
        gone_hard = [b for b in hard_blocks if b["form"] == "gone"]
        if visible_hard or gone_hard or missing:
            parts.append("")
            parts.append("## 2. Explicit References (Hard Signals)")
            for block in visible_hard:
                parts.append(_context_block_text(block, mode=mode))
            for block in gone_hard:
                parts.append(block.get("stub", CONTEXT_OMITTED_FMT.format(n=len(block["text"]))))
            for link in missing:
                parts.append(f"--- REFERENCE [[{link}]] NOT FOUND IN VAULT ---")
        visible_soft = [b for b in soft_blocks if b["form"] != "gone"]
        gone_soft = [b for b in soft_blocks if b["form"] == "gone"]
        if visible_soft or gone_soft:
            parts.append("")
            parts.append("## 3. Discovered Related Context (Soft Signals — Top-K Semantic/BM25)")
            for block in visible_soft:
                parts.append(_context_block_text(block, mode=mode))
            if gone_soft:
                omitted = sum(len(b["text"]) for b in gone_soft)
                parts.append(
                    f"... [omitted {omitted} characters to satisfy budget across "
                    f"{len(gone_soft)} related item(s)] ...")
        return "\n".join(parts)

    text = render()
    guard = 0
    while len(text) > budget and guard < 500:
        guard += 1
        block = next((b for b in order if b["form"] != "gone"), None)
        if block is None:
            text = text[:max(0, budget)]
            break
        form = block["form"]
        if form == "full":
            block["form"] = "summary"
        elif form == "summary":
            excess = len(text) - budget
            notice = CONTEXT_TRUNCATED_FMT.format(n=len(block["text"]))
            block["form"] = "trunc"
            block["limit"] = max(0, len(block["summary"]) - excess - len(notice))
        elif form == "trunc":
            excess = len(text) - budget
            block["limit"] = max(0, block.get("limit", 0) - excess)
            if block["limit"] == 0:
                block["form"] = "omit"
        elif form == "omit":
            # Hard/soft refs leave a one-line stub so nothing is dropped
            # silently; the target only vanishes as the very last resort.
            block["form"] = "stub" if block.get("stub") else "gone"
        else:  # stub -> gone
            block["form"] = "gone"
        text = render()
    return text


def cmd_context(vault_path, item_id, top_k=CONTEXT_DEFAULT_TOP_K,
                budget=CONTEXT_DEFAULT_BUDGET, mode="summary",
                no_semantic=False, reindex=False):
    """Assemble target + explicit wikilinks + Top-K BM25 matches (STORY-033)."""
    file_path = find_file_by_id(vault_path, item_id)
    if not file_path:
        print(f"Error: Item {item_id} not found.")
        sys.exit(1)

    rel_path = os.path.relpath(file_path, vault_path).replace(os.sep, "/")
    content = _context_read(vault_path, rel_path)
    if content is None:
        print(f"Error: could not read {file_path}")
        sys.exit(1)
    target_id = _context_doc_id(rel_path, content)
    target_title = _context_doc_title(content, rel_path)

    # Hard signals: deduplicated wikilinks, resolved against one index build.
    vault_index = build_vault_index(vault_path)
    links, seen = [], set()
    for raw_link in re.findall(r"\[\[(.*?)\]\]", content):
        name = raw_link.split("|")[0].split("#")[0].strip()
        if name and name not in seen:
            seen.add(name)
            links.append(raw_link)

    hard_blocks, missing = [], []
    hard_ids, hard_paths = set(), set()
    for link in links:
        name = link.split("|")[0].split("#")[0].strip()
        spec_path = _find_in_index(vault_index, name)
        if not spec_path:
            missing.append(link)
            continue
        spec_rel = os.path.relpath(spec_path, vault_path).replace(os.sep, "/")
        spec_text = _context_read(vault_path, spec_rel)
        if spec_text is None:
            missing.append(link)
            continue
        hard_ids.add(_context_doc_id(spec_rel, spec_text))
        hard_paths.add(spec_rel)
        hard_title, hard_snip = _context_hard_summary(spec_text)
        hard_blocks.append({
            "kind": "hard",
            "link": link,
            "path": spec_rel,
            "title": hard_title,
            "header": f"--- REFERENCE: [[{link}]] ---\nFile: {spec_rel}",
            "footer": "--- END OF REFERENCE ---",
            "meta": (),
            "text": spec_text,
            "summary": hard_snip,
            "stub": f"--- REFERENCE: [[{link}]] {CONTEXT_OMITTED_FMT.format(n=len(spec_text))} ---",
            "form": "full",
        })

    soft_blocks = []
    if not no_semantic:
        cache = context_cache_update(vault_path, force=reindex)
        surfaces = {}
        terms = _context_terms(content, surfaces=surfaces)
        tree = resolve_tree(vault_path)
        ranked = context_rank(
            cache, terms, surfaces=surfaces, top_k=top_k,
            exclude_ids=hard_ids | {target_id},
            exclude_paths=hard_paths | {rel_path}, tree=tree)
        best_score = ranked[0][1] if ranked else 0.0
        for row in ranked:
            doc_id, score, matched, path = row[0], row[1], row[2], row[3]
            best_ci = row[4] if len(row) > 4 else None
            doc_text = _context_read(vault_path, path)
            if doc_text is None:
                continue
            display = (score / best_score) if best_score else 0.0
            heading, excerpt = _context_extract_excerpt(
                doc_text, best_ci=best_ci, matched_terms=matched, max_chars=350)
            soft_blocks.append({
                "kind": "soft",
                "path": path,
                "score": display,
                "terms": matched,
                "terms_str": ", ".join(matched),
                "section": heading,
                "header": f"--- RELATED: [[{path}]] (Relevance Score: {display:.2f}) ---",
                "footer": "--- END OF RELATED ---",
                "meta": ((f"Matched terms: {', '.join(matched)}",) if matched else ()),
                "text": doc_text,
                "summary": excerpt,
                "stub": f"--- RELATED: [[{path}]] {CONTEXT_OMITTED_FMT.format(n=len(doc_text))} ---",
                "form": "full",
            })

    target_block = {
        "kind": "target",
        "header": "",
        "footer": "",
        "meta": (),
        "text": content,
        "summary": _context_target_summary(rel_path, content),
        "form": "full",
    }
    print(_context_assemble(target_id, target_title, target_block, hard_blocks,
                            missing, soft_blocks, budget, mode))
