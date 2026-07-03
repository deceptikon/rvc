---
domain: workflow_meta
domain_tags: ["rvc", "protocol"]

# HANDOVER — Domain-Based Vault Structuring

> Ready for a new session. Read this before starting.

---

## Context

RVC is being rebuilt. The tooling plan is locked (see `PLAN-RVC-REVIVAL.md`). The one undecided piece is how the vault organizes data by **domain**, so that `rvc context` doesn't become another MAP.md — a giant blob of linked everything.

## The Problem

When `rvc context STORY-05` runs, it needs to assemble relevant context. If it just follows all wikilinks, you get the MAP.md disaster: an unstructured graph of everything connected to everything. Useless.

The **flow-vault REGLAMENT** already defines two domains informally:
- **ADLAI Domain** — Saudi legal AI. RAG pipeline. Code. `backend/`, `frontend/`, `adlai-vault/`.
- **Workflow Domain** — Meta-project. Conductor. Vault protocol. CLI tooling. `20_Specs/L*.md`, `W_*.md`.

But this is prose, not structure. The system can't parse it.

## What We Need to Decide

1. **Domain definition** — How is a domain formally declared? A file? A frontmatter field? A directory? A tag?
2. **Story-to-domain binding** — How does STORY-05 declare "I belong to the retrieval domain"?
3. **Context scoping** — When `rvc context STORY-05` runs, how does it know to fetch retrieval-related specs but NOT infra-related ones?
4. **Cross-domain references** — How does a retrieval story reference an infra spec without pulling in the entire infra domain?
5. **Domain granularity** — Is "retrieval" a domain or a subdomain of "ADLAI"? How deep does the hierarchy go?

## What We Already Know

- The vault has 4 flat buckets: `issues/`, `specs/`, `artifacts/`, `meta/`
- Status is frontmatter-only
- No MAP.md — context is assembled on-the-fly from an in-memory index
- Cross-vault wikilinks: `[[vault-name:ID]]` syntax (future)
- We want depth-limited traversal, not full-graph injection

## Relevant Files to Read Before the Session

- `~/Q/vault-protocol/REGLAMENT.md` — the original RVC protocol spec
- `~/Q/GATHERING/flow-vault/00_Project/REGLAMENT.md` — flow-vault constitution (has domain separation rules)
- `~/Q/GATHERING/EPIC-GATHERING-MVP.md` — S-02 (Rebuild RVC context engine) and S-05 (Story quality contract)
- `~/Q/GATHERING/flow-vault/10_Issues/01_To_Do/EPIC-1-RVC-REVIVAL-WITH-FLOW.md` — the full EPIC
- `~/Q/GATHERING/flow-vault/20_Specs/` — all L0-L5 layer specs
- `~/Q/vault-protocol/vault-restructure.py` — current `generate_map()` and `infer_tags_from_content()` (the MAP.md monster we're killing)
- `~/Q/vault-protocol/rvc-cli.py` — current `cmd_context()` (the naive link-following we're replacing)

## What to Prepare Before the Session

- Read at minimum the flow-vault `REGLAMENT.md` and `EPIC-1-RVC-REVIVAL-WITH-FLOW.md`
- Think about what "domain" means in your context — is it a topic, a subsystem, a team, a vault?
- Have examples ready: which stories in your flow-vault belong to which domains? How would you tag them?

---

## Starting Prompt for the Session

> "We're designing the domain model for the RVC vault. The vault is `.RVC/` with 4 flat buckets. Issues are `.md` files with YAML frontmatter. We need to define how stories declare their domain, how context retrieval scopes to that domain, and how domains cross-reference without collapsing. Ready to discuss."
