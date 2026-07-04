---
id: STORY-010
type: story
status: To Do
priority: P0.0.0
assignee: "@ai-dev"
epic: "[[EPIC-002-Conductor-v0.2-Hardening]]"
created: 2026-06-28
tags: [conductor, issue, workflow, tdd, gates, p0, pipeline-tests]
title: Unit-Test-Foundation
domain: workflow_meta
domain_tags: ["rvc", "protocol", "story"]
aliases:
  - STORY-010
---

# STORY-010: Unit Test Foundation

## Context
Conductor had zero automated tests. The `test_fixtures/` directory was for manual QA gate testing only. The ASSEMBLY spec ([[0.0.0_ASSEMBLY]]) identifies the most critical systemic flaw: **no input validation at boundaries**. Every component trusted the previous component without verification.

This story establishes the pytest-based foundation covering the **entire pipeline** — every command in [[COMMANDS_REGISTRY]] and every stage in [[MAP]].

## Current State (as of 2026-07-04)

```
76 passed, 45 xfailed (RED) in 3.86s
```

**121 tests across 8 files**, organized by pipeline layer. RED tests use `pytest.mark.xfail(strict=True)` — they start failing (RED), and when an implementation story lands, removing the marker flips them GREEN.

## Test Files

| # | File | Coverage | GREEN | RED |
|---|------|----------|-------|-----|
| 1 | `tests/test_schema.py` | `Plan.validate()`, topo, node_map | 14 | 0 |
| 2 | `tests/test_workers.py` | `_strip_ansi`, `extract_stream_json`, `WorkerRegistry` | 18 | 0 |
| 3 | `tests/test_pipeline.py` | Serializers, graph build, routing, node contracts | 10 | 6 |
| 4 | `tests/test_rvc_cli.py` | All `rvc-cli` subcommands: get/context/issue/create/search/init/git-commit-all | 14 | 5 |
| 5 | `tests/test_conductor_cmds.py` | All `conductor` subcommands: run/approve/reject/edit/status/list/logs/selftest | 14 | 2 |
| 6 | `tests/test_gates.py` | G1–G6 gate contracts (ASSEMBLY.md) | 0 | 17 |
| 7 | `tests/test_pult_stages.py` | `pult gather/validate/inject/prompt/publish` (MAP stages 1a–1d, 11) | 0 | 14 |
| 8 | `tests/test_infra.py` | dash-client, session_bootstrap, rvc_mcp, agentic-bridge | 13 | 0 |

## Pipeline Stage → Test Mapping (MAP.md)

| MAP Stage | Command | Test File | RED because |
|-----------|---------|-----------|-------------|
| 0. rvc context | `rvc-cli context` | `test_rvc_cli.py` | GREEN ✅ |
| 1a. pult gather | `pult gather` | `test_pult_stages.py` | `conductor.pult` doesn't exist (STORY-95) |
| 1b. pult validate → G1/G2/G2.5/G3 | `pult validate` | `test_gates.py` + `test_pult_stages.py` | `conductor.gates` doesn't exist |
| 1c. pult inject | `pult inject` | `test_pult_stages.py` | STORY-96 |
| 1d. pult prompt | `pult prompt` | `test_pult_stages.py` | STORY-99 |
| 2. prompt_builder | STORY-101 service | `test_pipeline.py` | STORY-101 |
| 3. plan_node | `conductor run` | `test_pipeline.py` | GREEN (routing edges) |
| 4. review_node | `conductor run` | `test_pipeline.py` | GREEN (validation logic) |
| 5. approve_node | `conductor approve` | `test_conductor_cmds.py` | GREEN ✅ |
| 6. act_node | `conductor run` | `test_pipeline.py` | GREEN (graph compiles) |
| 7. bulk_node (conditional) | STORY-100 | `test_pipeline.py` | STORY-100 |
| 8. qa_node | `conductor run` | `test_pipeline.py` | GREEN (exit code routing) |
| 9. plan_reviser_node | `conductor run` | `test_pipeline.py` | GREEN (retry routing) |
| 10. commit_node | `conductor run` | `test_pipeline.py` | GREEN ✅ (git subprocess) |
| 11. pult publish | cross-vault artifact sync | `test_pult_stages.py` | STORY-102 |
| 12. dash-client push | `dash-client push` | `test_infra.py` | GREEN ✅ |
| 13. rvc git-commit-all | `rvc-cli git-commit-all` | `test_rvc_cli.py` | GREEN ✅ |

## RED → GREEN Path

| RED Group | Tests | Goes GREEN In | What changes |
|-----------|-------|---------------|--------------|
| `test_gates.py` (17) | G1–G6 contracts | STORY-94/95/96/97/101 | Create `conductor/gates.py` with `GateError`, `check_issue_file`, `validate_bootstrap_payload`, `check_rvc_reachable`, `check_phase_artifact`, `check_qa_passed`, `get_repo_root`, `check_canonical_spec` |
| `test_pult_stages.py` (14) | gather/validate/inject/prompt/publish | STORY-95/96/99/102 | Create `conductor/pult.py` with subcommand functions |
| `test_pipeline.py` (6) | bulk_node, prompt_builder, _check_rvc_reachable | STORY-100/101/95 | Add nodes to `build_graph()`, add helper to `pipeline.py` |
| `test_rvc_cli.py` (5) | cmd_init, create duplicate check, shell=True, _next_id race, find_vault_root | STORY-013 | Refactor rvc-cli.py: extract cmd_init, add exists() check, remove shell=True, add file locking |
| `test_conductor_cmds.py` (2) | cancel, retry subcommands | STORY-013 | Add subcommands to conductor CLI |

**Total: 45 RED → 121 tests.** When all GREEN: exit code 0, 121 passed, 0 xfailed.

## TDD Discipline

> **strict=True** means if a test *doesn't* fail, pytest reports it as `XPASS(strict)` — a hard error. This catches the "I think it's done but I forgot to remove the marker" lie. To make a test GREEN: remove the `xfail` marker from the test or module-level `pytestmark`, then verify it passes.

## How to Verify

```bash
cd ~/X/TEAMFLOW/conductor
uv run pytest tests/ -v          # verbose: see each test + RED/GREEN status
uv run pytest tests/ --tb=line   # compact: one-line per failure
uv run pytest tests/ -q          # summary only: 76 passed, 45 xfailed
```

## Files

```
conductor/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # shared fixtures: tmp_vault, tmp_git_repo, fake_worker, ...
│   ├── test_schema.py           # 14 tests — Plan.validate() [GREEN]
│   ├── test_workers.py          # 18 tests — stream parsing, registry [GREEN]
│   ├── test_pipeline.py         # 16 tests — graph build, routing, nodes [10G / 6R]
│   ├── test_rvc_cli.py          # 19 tests — all rvc-cli subcommands [14G / 5R]
│   ├── test_conductor_cmds.py   # 16 tests — all conductor subcommands [14G / 2R]
│   ├── test_gates.py            # 17 tests — G1-G6 gate contracts [RED]
│   ├── test_pult_stages.py      # 14 tests — pult subcommands [RED]
│   └── test_infra.py            # 13 tests — infra commands [GREEN]
├── pyproject.toml               # pytest config + testpaths
```
