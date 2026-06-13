#!/usr/bin/env python3
"""
vault-restructure.py — One-shot + periodic vault restructuring tool.

Goals:
  1. Ensure every .md file has valid, consistent frontmatter.
  2. Auto-wrap plain-text STORY-XX / EPIC-XX references in [[wikilinks]].
  3. Add missing domain tags based on content analysis.
  4. Generate MAP.md — a navigable knowledge-graph index.
  5. Be idempotent — safe to re-run.

Usage:
  python3 vault-restructure.py /path/to/vault [--dry-run]

Importable API:
  from vault_restructure import rescan_vault
  summary = rescan_vault("/path/to/vault", dry_run=False)
"""

import os
import re
import sys
import json
import hashlib
from collections import defaultdict
from datetime import date

SKIP_DIRS = {".obsidian"}

# ---------------------------------------------------------------------------
# Known IDs discovered in the vault
# ---------------------------------------------------------------------------
STORY_RE = re.compile(r'\b(STORY-\d+)\b')
EPIC_RE = re.compile(r'\b(EPIC-\d+)\b')  # only matches EPIC-01..EPIC-09
ID_RE = re.compile(r'\b((?:STORY|EPIC)-\d+)\b')

# Domain keyword → tag mapping (order matters — first match wins per category)
DOMAIN_TAG_RULES = [
    # retrieval pipeline
    (["retrieval", "recall", "retriever", "bm25", "pgvector", "dense",
      "sparse", "hybrid", "chunk", "chunking", "index", "indexing"],
     "retrieval"),
    # ingestion / corpus
    (["ingest", "ingestion", "corpus", "scrape", "scraper", "crawl",
      "law_type", "source_file", "chunk_text", "section_ref"],
     "ingestion"),
    # reranker
    (["rerank", "reranker", "cross-encoder", "bge-reranker", "re-rank"],
     "reranker"),
    # LLM / inference
    (["llm", "allam", "qwen", "frontier", "llama-server", "llama.cpp",
      "n_ctx", "max_tokens", "kv cache", "inference", "generation",
      "model", "prompt", "temperature", "top_p", "top_k"],
     "llm"),
    # routing
    (["routed", "router", "routing", "sovereign", "classifier",
      "reasoning", "ReasoningRouter"],
     "routing"),
    # citation / verifier
    (["citation", "verifier", "verify", "verif", "article_num",
      "material", "cited", "ground"],
     "citation"),
    # eval
    (["eval", "evaluation", "benchmark", "metric", "accuracy", "precision",
      "recall@", "ret@", "g_recall", "cite_rate", "mean_latency"],
     "eval"),
    # verifier specifics
    (["hallucin", "hallucination", "masking", "retry loop"],
     "verifier"),
    # performance / infra
    (["latency", "throughput", "concurrent", "parallel", "async", "lock",
      "thread", "worker", "gpu", "vps", "cpu", "memory", "oom",
      "docker", "deploy", "infra", "server"],
     "infra"),
    # database
    (["postgres", "pgvector", "database", "schema", "sql", "migration",
      "table", "corpus table", "repository"],
     "database"),
    # frontend
    (["frontend", "vue", "vite", "ui", "ux", "component", "css", "tailwind",
      "browser", "citation panel"],
     "frontend"),
    # vertical / domain
    (["zatca", "sama", "pdpl", "misa", "nca", "cma", "moj",
      "vertical", "regulation", "saudi"],
     "vertical"),
    # attorney / review queue
    (["attorney", "review queue", "human review", "few-shot", "flywheel",
      "approval", "queue"],
     "review-queue"),
    # data quality
    (["ground-truth", "ground truth", "oracle", "expected_citations",
      "accepted_answer", "dataset audit", "data-quality"],
     "data-quality"),
    # observability
    (["observab", "monitor", "log", "health", "watch", "aiwatch",
      "runbook", "alert"],
     "observability"),
    # NLP / Arabic
    (["arabic", "rtl", "stemm", "stemmer", "normali", "tokeniz",
      "cross-lingual", "bilingual", " translated"],
     "nlp"),
    # testing
    (["pytest", "test", "tdd", "unittest", "integration test",
      "unit test", "test_"],
     "testing"),
    # CI/CD
    (["ci/cd", "gitlab", "pipeline", "pre-commit", "ruff", "lint",
      "format", "deploy", "dockerfile"],
     "cicd"),
]

# Files whose names suggest a domain (filename → tag)
FILENAME_TAG_RULES = [
    (["retrieval", "rerank", "bm25", "chunk", "hybrid", "dense", "sparse"],
     "retrieval"),
    (["ingest", "scraper", "corpus", "re-ingest"], "ingestion"),
    (["eval", "benchmark", "metric", "grading", "audit"], "eval"),
    (["citation", "verif", "hallucin", "mask"], "citation"),
    (["router", "routing", "sovereign", "classif"], "routing"),
    (["llm", "prompt", "infer", "allam", "qwen", "frontier"], "llm"),
    (["frontend", "ui", "ux", "panel", "component"], "frontend"),
    (["deploy", "vps", "docker", "infra", "server", "parallel",
      "latency", "throughput", "concurrency"], "infra"),
    (["database", "schema", "postgres", "migration", "pgvector"], "database"),
    (["zatca", "sama", "pdpl", "misa", "nca", "cma", "moj", "vertical"],
     "vertical"),
    (["attorney", "queue", "review", "flywheel", "few-shot"], "review-queue"),
    (["observab", "runbook", "watch", "health"], "observability"),
    (["arabic", "nlp", "stemm", "normali", "rtl"], "nlp"),
    (["test", "tdd", "unittest"], "testing"),
    (["cicd", "pipeline", "lint", "format", "pre-commit"], "cicd"),
    (["deploy", "cicd", "dockerfile"], "cicd"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(content):
    """Return (frontmatter_dict, frontmatter_raw, body_start_offset)."""
    if not content.startswith("---"):
        return {}, "", 0
    end = content.find("---", 3)
    if end < 0:
        return {}, "", 0
    raw = content[3:end].strip()
    fm = {}
    for line in raw.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip().lower()
        v = v.strip()
        # Strip quotes
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        elif v.startswith("'") and v.endswith("'"):
            v = v[1:-1]
        fm[k] = v
    return fm, raw, end + 3


def fm_to_yaml(fm):
    """Convert dict to YAML frontmatter string."""
    lines = []
    for k, v in fm.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                items = ", ".join(str(i) for i in v)
                lines.append(f"{k}: [{items}]")
        elif isinstance(v, str):
            # Quote if it contains special chars
            if any(c in v for c in ':[]#{}>*|`@"\'\n'):
                lines.append(f'{k}: "{v}"')
            else:
                lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n"


def infer_tags_from_content(content, filename):
    """Infer domain tags from content keywords + filename."""
    text = (content + " " + filename).lower()
    tags = set()
    for keywords, tag in DOMAIN_TAG_RULES:
        for kw in keywords:
            if kw.lower() in text:
                tags.add(tag)
                break
    for keywords, tag in FILENAME_TAG_RULES:
        fname_lower = filename.lower()
        for kw in keywords:
            if kw.lower() in fname_lower:
                tags.add(tag)
                break
    return sorted(tags)


def find_known_ids(vault_root):
    """Build a set of all known STORY-XX and EPIC-XX IDs from filenames."""
    known = set()
    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            m = re.match(r'((?:STORY|EPIC)-\d+)', f)
            if m:
                known.add(m.group(1))
    return known


def wrap_plain_ids(content_body, known_ids, self_id=None):
    """
    Wrap plain-text STORY-XX / EPIC-XX references in [[wikilinks]].
    Skip self-references and already-wrapped links.
    Returns (new_body, count_of_additions).
    """
    # Remove existing [[...]] links from consideration
    # First, find all already-wrapped IDs
    already_wrapped = set()
    for m in re.finditer(r'\[\[(.*?)\]\]', content_body):
        inner = m.group(1).split('|')[0].strip()
        already_wrapped.add(inner)

    additions = 0
    result = content_body
    # Process IDs longest-first to avoid partial matches
    for id_str in sorted(known_ids, key=len, reverse=True):
        if id_str == self_id:
            continue
        if id_str in already_wrapped:
            continue
        # Replace plain text [[NOT in brackets]] with [[wikilink]]
        # Use a regex that avoids matching inside [[...]], code blocks, or URLs
        pattern = re.compile(
            r'(?<!\[)'           # not preceded by [
            r'(?<!\[\[)'         # not preceded by [[
            r'\b(' + re.escape(id_str) + r')\b'
            r'(?!\])'            # not followed by ]
            r'(?!\]\])'          # not followed by ]]
        )

        def replacer(m):
            nonlocal additions
            additions += 1
            return f"[[{m.group(1)}]]"

        result = pattern.sub(replacer, result)

    return result, additions


def normalize_frontmatter(fm, filepath, filename, vault_root):
    """Ensure consistent frontmatter fields. Returns (fm, changed)."""
    changed = False
    base = os.path.basename(filepath)
    rel = os.path.relpath(filepath, vault_root)

    # Determine type from path if missing
    if "type" not in fm:
        if "/20_Specs/" in filepath:
            fm["type"] = "spec"
        elif "/20_Reviews/" in filepath:
            fm["type"] = "review"
        elif "/20_Review" in filepath:
            fm["type"] = "review"
        elif "/90_Assets/" in filepath:
            fm["type"] = "asset"
        elif "/99_Archive/" in filepath:
            fm["type"] = "archive"
        elif "/00_Project/" in filepath:
            fm["type"] = "meta"
        changed = True

    # Extract ID from filename if not in frontmatter
    m = re.match(r'((?:STORY|EPIC)-\d+)', base)
    file_id = m.group(1) if m else None

    if file_id:
        if "id" not in fm:
            fm["id"] = file_id
            changed = True
        if "title" not in fm and fm.get("type") in ("story", "epic"):
            # Derive title from filename: remove ID prefix
            title = base.replace(".md", "")
            title = re.sub(r'^(STORY|EPIC)-\d+-?', '', title).strip()
            # Remove parenthetical suffixes
            title = re.sub(r'\s*\(playwright\)\s*', '', title)
            title = re.sub(r'\s*\(superseded.*?\)\s*', '', title).strip()
            if title:
                fm["title"] = title
                changed = True

    # Normalize status values
    status_map = {
        "to do": "To Do",
        "to_do": "To Do",
        "active": "Active",
        "in progress": "Active",
        "in_progress": "Active",
        "review": "Review",
        "done": "Done",
        "closed": "Done",
        "backlog": "Backlog",
    }
    if "status" in fm:
        s = fm["status"].strip().lower()
        if s in status_map and fm["status"] != status_map[s]:
            fm["status"] = status_map[s]
            changed = True
    # For done files, ensure status is Done
    if "/04_Done/" in filepath and fm.get("status") not in ("Done", None):
        fm["status"] = "Done"
        changed = True
    elif "/02_Active/" in filepath and fm.get("status") not in ("Active", None):
        fm["status"] = "Active"
        changed = True
    elif "/03_Review/" in filepath and fm.get("status") not in ("Review", None):
        fm["status"] = "Review"
        changed = True
    elif "/01_To_Do/" in filepath and fm.get("status") not in ("To Do", None):
        fm["status"] = "To Do"
        changed = True
    elif "/00_Backlog/" in filepath and fm.get("status") not in ("Backlog", None):
        fm["status"] = "Backlog"
        changed = True

    # Normalize priority to P0..P3
    if "priority" in fm:
        p = fm["priority"].strip()
        if p.upper() in ("P0", "P1", "P2", "P3"):
            if fm["priority"] != p.upper():
                fm["priority"] = p.upper()
                changed = True
        elif p.lower() in ("critical", "high", "medium", "low"):
            mapping = {"critical": "P0", "high": "P1", "medium": "P2", "low": "P3"}
            fm["priority"] = mapping[p.lower()]
            changed = True

    # Normalize epic field — ensure it's in [[wikilink]] format
    if "epic" in fm:
        epic_val = fm["epic"].strip()
        epic_id = re.search(r'(EPIC-\d+)', epic_val)
        if epic_id:
            normalized = f"[[{epic_id.group(1)}]]"
            if epic_val != normalized:
                fm["epic"] = normalized
                changed = True

    # Merge inferred tags with existing tags
    existing_tags = set()
    if "tags" in fm:
        raw_tags = fm["tags"].strip()
        if raw_tags.startswith("[") and raw_tags.endswith("]"):
            raw_tags = raw_tags[1:-1]
        existing_tags = {t.strip() for t in raw_tags.split(",") if t.strip()}

    return fm, changed


def reconcile_tags(fm, filepath, filename, body):
    """Merge inferred domain tags into frontmatter tags."""
    existing = set()
    if "tags" in fm:
        raw = fm["tags"].strip()
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        existing = {t.strip() for t in raw.split(",") if t.strip()}

    inferred = set(infer_tags_from_content(body + " " + filename, filename))
    merged = sorted(existing | inferred)

    if "tags" not in fm or set(t.strip() for t in fm["tags"].strip("[]").split(",") if t.strip()) != set(merged):
        fm["tags"] = merged
        return True
    return False


def process_file(filepath, known_ids, vault_root, dry_run=False):
    """Process a single file. Returns dict of actions taken."""
    actions = []
    with open(filepath, "r") as f:
        original = f.read()

    filename = os.path.basename(filepath)
    fm, fm_raw, body_start = parse_frontmatter(original)
    body = original[body_start:]

    # 1. Normalize frontmatter
    fm_changed = False
    fm, fm_changed = normalize_frontmatter(fm, filepath, filename, vault_root)

    # 2. Reconcile tags
    body_for_tags = body + " " + original[:body_start]  # include FM in analysis
    tags_changed = reconcile_tags(fm, filepath, filename, body_for_tags)

    # 3. Wrap plain-text IDs in wikilinks (body only)
    self_id_match = re.match(r'((?:STORY|EPIC)-\d+)', filename)
    self_id = self_id_match.group(1) if self_id_match else None
    new_body, link_count = wrap_plain_ids(body, known_ids, self_id)

    if link_count > 0:
        body = new_body
        actions.append(f"+{link_count} wikilinks")

    if tags_changed:
        actions.append("tags updated")

    if fm_changed:
        actions.append("frontmatter normalized")

    # Rebuild file content
    new_fm_yaml = fm_to_yaml(fm)
    new_content = new_fm_yaml + "\n" + body.lstrip("\n")

    # Only write if content actually changed
    if new_content != original:
        if not dry_run:
            with open(filepath, "w") as f:
                f.write(new_content)
        actions.append("written")
    elif actions:
        actions.append("content-same")

    return {
        "file": os.path.relpath(filepath, vault_root),
        "actions": actions,
        "new_fm": fm,
        "new_content": new_content,
    }


def generate_map(results, vault_root):
    """Generate MAP.md — a navigable knowledge graph index."""
    # Build lookup: id → {file, type, status, tags, wikilinks}
    by_id = {}
    by_type = defaultdict(list)
    by_status = defaultdict(list)
    by_tag = defaultdict(list)
    all_wikilinks = defaultdict(set)  # source_id → {target_ids}

    for r in results:
        fm = r["new_fm"]
        fid = fm.get("id")
        ftype = fm.get("type", "")
        status = fm.get("status", "unknown")
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]

        if fid:
            by_id[fid] = r
        by_type[ftype].append(r)
        by_status[status].append(r)
        for t in tags:
            by_tag[t].append(r)

    # Discover outbound wikilinks from the new_fm + body stored in results
    # We re-read the new content from results (works for both dry-run and live)
    for r in results:
        fid = r["new_fm"].get("id")
        if not fid:
            continue
        # Reconstruct the new content to scan for wikilinks
        new_content = r.get("new_content", "")
        if not new_content:
            # Fallback: read from disk (live mode)
            fp = os.path.join(vault_root, r["file"])
            if os.path.exists(fp):
                with open(fp) as f:
                    new_content = f.read()
        targets = set(ID_RE.findall(new_content))
        targets.discard(fid)
        if targets:
            all_wikilinks[fid] = targets

    lines = []
    lines.append("---")
    lines.append("type: meta")
    lines.append("title: Vault Knowledge Map")
    lines.append(f"updated: {date.today().isoformat()}")
    lines.append("tags: [map, index, knowledge-graph]")
    lines.append("---")
    lines.append("")
    lines.append("# 🗺️ ADLAI Vault Knowledge Map")
    lines.append("")
    lines.append(f"*Auto-generated — {date.today().isoformat()}. Safe to regenerate.*")
    lines.append("")
    lines.append("## Quick Index")
    lines.append("")
    lines.append("| Symbol | Meaning |")
    lines.append("|---|---|")
    lines.append("| `[[ID]]` | Wikilink to a story/epic |")
    lines.append("| `#tag` | Domain filter tag |")
    lines.append("| ✅ Done / 🔍 Review / ▶ Active / ⬜ To Do / 📋 Backlog | Status |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # EPICs section
    epics = sorted(by_type.get("epic", []), key=lambda r: r["new_fm"].get("id", ""))
    if epics:
        lines.append("## Epics")
        lines.append("")
        for r in epics:
            fm = r["new_fm"]
            eid = fm.get("id", "?")
            title = fm.get("title", r["file"])
            status = fm.get("status", "?")
            tags = fm.get("tags", [])
            tag_str = " ".join(f"`{t}`" for t in tags[:5]) if tags else ""
            status_icon = {"Done": "✅", "Review": "🔍", "Active": "▶"}.get(status, "⬜")
            lines.append(f"- {status_icon} [[{eid}]] — {title} {tag_str}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Stories by status
    status_order = ["Active", "Review", "To Do", "Backlog", "Done"]
    status_icons = {"Active": "▶", "Review": "🔍", "To Do": "⬜", "Backlog": "📋", "Done": "✅"}
    stories = by_type.get("story", [])
    if stories:
        for status in status_order:
            bucket = [r for r in stories if r["new_fm"].get("status") == status]
            if not bucket:
                continue
            icon = status_icons.get(status, "⬜")
            lines.append(f"## {icon} {status} ({len(bucket)})")
            lines.append("")
            for r in sorted(bucket, key=lambda x: x["new_fm"].get("id", "")):
                fm = r["new_fm"]
                sid = fm.get("id", "?")
                title = fm.get("title", r["file"])
                tags = fm.get("tags", [])
                tag_str = " ".join(f"`{t}`" for t in tags[:4]) if tags else ""
                epic = fm.get("epic", "")
                epic_ref = f" ← {epic}" if epic else ""
                lines.append(f"- [[{sid}]] — {title} {tag_str}{epic_ref}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Specs
    specs = by_type.get("spec", [])
    if specs:
        lines.append("## 📐 Specs")
        lines.append("")
        for r in sorted(specs, key=lambda x: x["file"]):
            fm = r["new_fm"]
            title = fm.get("title", r["file"])
            tags = fm.get("tags", [])
            tag_str = " ".join(f"`{t}`" for t in tags[:4]) if tags else ""
            lines.append(f"- {r['file']} — {title} {tag_str}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Reviews
    reviews = by_type.get("review", [])
    if reviews:
        lines.append("## 📝 Reviews")
        lines.append("")
        for r in sorted(reviews, key=lambda x: x["file"]):
            fm = r["new_fm"]
            title = fm.get("title", r["file"])
            lines.append(f"- {r['file']} — {title}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Domain Tags Index
    if by_tag:
        lines.append("## 🏷️ By Domain Tag")
        lines.append("")
        for tag in sorted(by_tag.keys()):
            refs = by_tag[tag]
            ids = [r["new_fm"].get("id", r["file"]) for r in refs if r["new_fm"].get("id")]
            link_ids = [f"[[{i}]]" for i in sorted(ids)]
            lines.append(f"**#{tag}** ({len(refs)}): {', '.join(link_ids) if link_ids else ', '.join(r['file'] for r in refs)}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Relationship graph (wikilinks)
    if all_wikilinks:
        lines.append("## 🔗 Cross-References")
        lines.append("")
        lines.append("```")
        for src_id in sorted(all_wikilinks.keys()):
            targets = sorted(all_wikilinks[src_id])
            if targets:
                lines.append(f"[[{src_id}]] → {', '.join(f'[[{t}]]' for t in targets)}")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rescan_vault(vault_root, dry_run=False, skip_map=False):
    """
    Rescan and restructure the vault. Returns a summary dict.

    Args:
        vault_root: Absolute path to the vault directory.
        dry_run: If True, don't write any files.
        skip_map: If True, don't regenerate MAP.md.

    Returns:
        dict with keys: files_processed, files_changed, wikilinks_added, results
    """
    vault_root = os.path.abspath(vault_root)
    known_ids = find_known_ids(vault_root)

    results = []
    changed_files = 0
    total_links = 0

    for root, dirs, files in os.walk(vault_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            fp = os.path.join(root, f)
            r = process_file(fp, known_ids, vault_root, dry_run)
            results.append(r)
            if "written" in r["actions"]:
                changed_files += 1
            if any("wikilinks" in a for a in r["actions"]):
                for a in r["actions"]:
                    m = re.search(r'\+(\d+) wikilinks', a)
                    if m:
                        total_links += int(m.group(1))

    # Generate MAP.md
    map_path = os.path.join(vault_root, "00_Project", "MAP.md")
    if not skip_map:
        map_content = generate_map(results, vault_root)
        if not dry_run:
            os.makedirs(os.path.dirname(map_path), exist_ok=True)
            with open(map_path, "w") as f:
                f.write(map_content)

    return {
        "files_processed": len(results),
        "files_changed": changed_files,
        "wikilinks_added": total_links,
        "map_path": map_path if not skip_map else None,
        "results": results,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    vault_root = sys.argv[1] if len(sys.argv) > 1 else "."
    dry_run = "--dry-run" in sys.argv
    skip_map = "--skip-map" in sys.argv

    print(f"Vault: {vault_root}")
    print(f"Mode:  {'DRY RUN (no writes)' if dry_run else 'LIVE'}")
    print()

    summary = rescan_vault(vault_root, dry_run=dry_run, skip_map=skip_map)

    print(f"Known IDs: {sorted(find_known_ids(vault_root))}")
    print()
    if summary["map_path"]:
        print(f"MAP.md: {summary['map_path']}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Files processed: {summary['files_processed']}")
    print(f"Files changed:   {summary['files_changed']}")
    print(f"Wikilinks added: {summary['wikilinks_added']}")

    # Show per-file
    print()
    for r in summary["results"]:
        if r["actions"] and "content-same" not in r["actions"]:
            action_str = ", ".join(r["actions"])
            print(f"  {r['file']}: {action_str}")


if __name__ == "__main__":
    main()
