---
doc_id: architecture-overview
domain: agentlayer_docs
tags: [architecture, overview]
---

## What it is

AgentLayer is an OpenAI-compatible HTTP API + tool runtime around local models (Ollama), with:

- a **tool registry** that loads Python tools from disk
- a **planner/executor tool loop** (`src/domain/agent.py`)
- a **first-party UI** (`interfaces/agent-ui/`)
- **workspaces** (generic dashboards: layout + JSON data + sharing)

## Main components

### HTTP API server

- Entry: `src/api/main.py`
- Chat: `src/domain/agent.py::chat_completion`
- Workspace endpoints: `src/workspace/router.py`
- Tool execution endpoint: `src/domain/plugin_system/tools_api.py` (router)

### Tool runtime

- Registry scanning: `src/domain/plugin_system/registry.py`
- Tool execution: `src/domain/tool_executor.py` and `src/domain/plugin_system/tools.py`
- Capabilities: `docs/adr/0002-tool-capabilities-convention.md`
- Capability gates: `docs/adr/0003-capability-governance.md`

### Storage (Postgres)

- Migrations: `src/infrastructure/db/migrations/`
- Schema snapshot: `src/infrastructure/db/migrations/sql/schema.sql`
- DB helpers: `src/infrastructure/db/db.py`

### UI (agent-ui)

- Workspace page: `interfaces/agent-ui/src/pages/WorkspacePage.tsx`
- Workspace blocks: `interfaces/agent-ui/src/features/workspace/WorkspaceBlocks.tsx`

## Data flows (high level)

### Chat with tools

1. Client calls `POST /v1/chat/completions` (OpenAI-compatible).
2. `src/domain/agent.py` merges tool specs from the registry.
3. The model may return tool calls.
4. AgentLayer runs tool calls deterministically via the Executor.
5. Tool results are appended as messages; loop continues for a few rounds.

See ADR 0001: `docs/adr/0001-tool-and-agent-architecture.md`.

### Workspaces

1. UI calls `GET /v1/workspaces` to list and load the catalog metadata.
2. UI calls `POST /v1/workspaces` to create a workspace from an installed template kind.
3. UI persists layout+data to the backend via workspace update endpoints.

Workspaces are generic (kind + layout + data). Specific “apps” (pets/shopping) are templates + optional tools.

