---
id: EPIC-001
type: epic
priority: P0
assignee: "@ai-dev"
created: 2026-04-23
title: RVC-Protocol
tags: [issue, workflow]
domain: workflow_meta
domain_tags: [rvc, protocol]
aliases:
  - EPIC-001
deferred: 2026-09-29
---
> **Domain:** [[VAULT_DOMAINS]] #rvc


# EPIC-001: The RVC Local-First Protocol

## 2026-09-29 — DEFERRED: a 2026-04 wishlist pinned at the top of the ready queue

This epic was parked P0 in `20_NEXT`, which the plate renders as the *first line of the queue* — the
position a reader's eye lands on. It is not work. It is a container whose requirement list has
drifted five months from what the project actually decided, and leaving it there spends the most
valuable square inch of the plate on a document.

**The requirements that are not protocol.** `Obsidian Templater Suite`, `Advanced Dashboards`
(Canvas/Kanban) and `Graph DB Integration` are *products*, not protocol, and two of them were
already superseded and archived: STORY-004/005/006 sit in `90_ARCHIVE/superseded/`. A graph
backend is the explicit anti-goal of EPIC-004's design core — "no second state store — that is the
bug class that killed v5.3". Re-adopting it here is a contradiction living in the queue.

**The requirements that shipped under other numbers.** Context-aware CLI/MCP (STORY-001, -003,
-033, -034, -037, -038) and Git-sync (STORY-007) are done, but the boxes are unticked because
nobody came back to a five-month-old checklist. The two unchecked items on the *milestone* list —
"RVC Scaffolder" (STORY-002) and "Graph DB" — are likewise a done thing and an archived thing.

**Re-entry condition.** Re-cut this epic against what the protocol *is* after the 2026-09-29 state
pass: folder-as-state, the plate as the only renderer, one generated formal artefact (`rvc ask`),
and one live wire. Do not restore it to `20_NEXT` until the re-cut is written — a P0 epic that is
not actionable at the top of the queue is worse than no epic, because it trains the reader to
ignore the top of the queue.

## Problem Statement
Business owners struggle with GitHub/Lab UI; AI devs suffer from fragmented context and access issues. Info duplication causes tracking chaos.

## Goal
Reinvent MD-file based issue and context handling. A local-first source of truth that humans use via Obsidian and AIs use via standardized CLI/MCP tools.

## Requirements
- [x] Standardized Directory Structure (RVC v1.0).
- [ ] Context-aware CLI/MCP Tooling ([[STORY-001-Lifecycle-Automation]], [[STORY-003-RVC-MCP-Server]]).
- [ ] Visual Dashboards (Canvas/Kanban) ([[STORY-004-Obsidian-Templates]], [[STORY-005-Advanced-Dashboards]]).
- [ ] Graph DB Connectivity ([[STORY-006-Graph-DB-Integration]]).
- [ ] Git-Sync Automation ([[STORY-007-Git-Sync-Automation]]).
