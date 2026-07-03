---
type: meta
tags: [workflow]
domain: workflow_meta
domain_tags: ["rvc", "protocol"]
---

# RVC Evolution Roadmap

The goal is to move from a set of scripts to a **God Mode** protocol that orchestrates human and AI devs with zero friction.

## Milestones
- [x] **Core Lifecycle Automation** ([[STORY-001]]): Status shifting logic.
- [ ] **RVC Scaffolder** ([[STORY-002]]): `rvc init` command.
- [x] **Real MCP Server Integration** ([[STORY-003]]): Proper agent tool discovery.
- [ ] **Obsidian Templater Suite** ([[STORY-004]]): Standardized entry for Humans.
- [ ] **Advanced Dashboards** ([[STORY-005]]): Canvas/Kanban views.
- [ ] **Graph DB Integration** ([[STORY-006]]): Neo4j or unified graph backend.
- [x] **Git-Sync Automation** ([[STORY-007]]): State locking and sync rules.
- [ ] **Conductor v0.2 Hardening** ([[EPIC-002]]): Security, PlanReviser, tests, parallel execution.

## Current Quarter Focus (Q3 2026)
1. **RVC Protocol Security & Performance** — Eliminate `shell=True`, add vault indexing, fix race conditions.
2. **Conductor Intelligence** — Replace PlanReviser stub with real diagnosis, add unit tests, enable parallel DAG execution.
3. **Integration Polish** — Auto-transition RVC issues after conductor commits, cache RVC context, optimize token usage.
