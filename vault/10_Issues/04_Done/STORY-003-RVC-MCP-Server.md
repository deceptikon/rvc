---
id: STORY-003
type: story
status: Done
priority: Critical
assignee: "@ai-dev"
epic: "[[EPIC-001]]"
created: 2026-04-23
---
# STORY-003: Global RVC MCP Server & Unified Graph Storage

## Description
Running an MCP server and graph database per-project is resource-heavy and a fragmented nightmare. We need ONE centralized MCP Server running globally.

### Architecture:
1. **Global Daemon (`rvcd`)**: A single FastMCP instance running on the host machine.
2. **Multi-Tenant Context**: Tools accept an optional `project_id` or auto-detect context based on the active workspace path passed by the LLM client.
3. **Unified Graph DB**: One central graph storage (e.g., local Neo4j or unified vector DB). Nodes MUST have a `project` property. This enables cross-project linking (e.g., ADLAI API specs linking to massage.kg frontend integration).
4. **Tool Interfaces**: Expose the tree-style commands from `STORY-001` natively to the agents via MCP (`rvc_issue_start`, `rvc_project_info`, etc.).