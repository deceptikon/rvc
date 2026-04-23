---
id: STORY-003
type: story
status: To Do
priority: Medium
assignee: "@ai-dev"
created: 2026-04-23
---
# STORY-003: Real RVC MCP Server (Native Agent Discovery)

## Description
Python CLI is good, but a formal MCP server is better. It allows agents to "see" the RVC tools natively in their system prompt.
Requirements:
1. Implement using `FastMCP` or a standard Python MCP library.
2. Provide tools: `rvc_get_issue`, `rvc_get_context`, `rvc_move_issue`.
3. Allow the agent to search the vault using vector search (Graph-prep).
