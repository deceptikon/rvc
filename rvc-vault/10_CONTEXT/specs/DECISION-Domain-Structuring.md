---
domain: workflow_meta
domain_tags: ["rvc", "protocol", "decision"]
---

# DECISION: Domain-Based Structuring

**Session Date:** 2026-07-03  
**Status:** DECIDED

This document records the decisions made during the domain structuring session for the RVC vault protocol. It answers the five open questions from `HANDOVER.md` and establishes the canonical rules for domain declaration, story-to-domain binding, context scoping, cross-domain references, and granularity.

---

## 1. Domain Definition — How is a domain formally declared?

A domain is declared by `domain_id` in `VAULT_DOMAINS.md`. The `domain_id` is the value used in frontmatter (e.g., `workflow_meta`, `infrastructure`). No new file format is required.

Each `domain_id` is registered under a top-level family (`adlai` or `workflow`). The registry in `VAULT_DOMAINS.md` is the source of truth for valid domain IDs.

---

## 2. Story-to-Domain Binding — How does a story declare its domain?

Stories use the existing `domain:` frontmatter key. The value must be a `domain_id` registered in `VAULT_DOMAINS.md`.

Example:
```yaml
---
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
---
```

The `domain_tags:` key is optional and provides additional tags for filtering or indexing.

---

## 3. Context Scoping — How does `rvc context` scope to the right domain?

`rvc context STORY-XX` performs depth-limited traversal (default depth = 2). It includes linked files only if they satisfy one of the following conditions:

- **(a) Same top-level family:** The linked file's `domain:` value belongs to the same top-level family (`adlai` or `workflow`) as the source story.
- **(b) Hub files:** The linked file is a hub file (exempt from family filtering). Hub files include: `ROUTING`, `REGLAMENT`, `VAULT_DOMAINS`, `WORKFLOW_LAYERS`.
- **(c) Cross-vault linked:** The link uses the `[[vault-name:ID]]` syntax and points to a file in another vault.

Files in a different top-level family are skipped unless they are hub files or cross-vault links.

---

## 4. Cross-Domain References — How to reference another domain without pulling it all in?

Use the `[[vault-name:ID]]` syntax. The target is included as a **single leaf**; its outbound links are NOT followed. This prevents domain collapse.

Example:
```markdown
See [[adlai-vault:ROUTING]] for the routing spec.
```

This includes only the content of `ROUTING.md` from the `adlai-vault` without traversing its outbound links.

---

## 5. Domain Granularity — How deep does hierarchy go?

Exactly 2 levels: `top-level/subdomain`. The `domain:` frontmatter uses the leaf subdomain ID. No deeper nesting is allowed.

Examples:
- ✅ `workflow_meta` (workflow + meta)
- ✅ `retrieval` (adlai + retrieval)
- ❌ `workflow/meta/subdomain` (3 levels — not allowed)

---

## Domain ID Registry

| domain_id | top_level_family | description |
|-----------|------------------|-------------|
| `workflow_meta` | workflow | RVC protocol, session ritual, artifacts, agent tooling |
| `workflow` | workflow | Core workflow ritual (SYNC, ENGAGE, ACT, WRAP) |
| `infrastructure` | adlai | Database, Docker, CI/CD, deployment |
| `retrieval` | adlai | Hybrid RAG, ingestion, chunking, bm25, pgvector |
| `llm_inference` | adlai | LLM routing, inference stack, prompts |
| `citation` | adlai | Citation verification, legal source matching |
| `corpus` | adlai | Legal corpus, verticals, Saudi regulations |
| `review_queue` | adlai | Attorney review, confidence gating, risk levels |
| `frontend` | adlai | Vue UI, bilingual UX, RTL |

---

## Context Scoping Algorithm

1. Start from the source story file.
2. Traverse outbound wikilinks up to `default_depth` (2).
3. For each linked file:
   - Resolve the target file path.
   - Read its `domain:` frontmatter value.
   - If `domain:` is missing, skip the file.
   - If the file is a hub file, include it.
   - If the file's top-level family matches the source, include it.
   - If the link is a cross-vault link (`[[vault-name:ID]]`), include it as a single leaf.
   - Otherwise, skip the file.
4. Return the collected context.

---

## Cross-Domain Reference Rule

When a story references a file in a different top-level family:
- Use `[[vault-name:ID]]` syntax.
- The target is included as a single leaf.
- Outbound links from the target are NOT followed.
- This prevents domain collapse and keeps context scoped.

---

## Granularity Policy

- Maximum depth: 2 levels (`top-level/subdomain`).
- The `domain:` frontmatter uses the leaf subdomain ID.
- No deeper nesting is allowed.
- Top-level families: `adlai`, `workflow`.

---

## References

- [[HANDOVER]] — Pre-session briefing with 5 open questions.
- [[rvc-vault/00_Project/PLAN-RVC-REVIVAL]] — Plan document with NOT DECIDED marker.
- [[../20_Specs/VAULT_DOMAINS]] — Domain taxonomy and registry.
