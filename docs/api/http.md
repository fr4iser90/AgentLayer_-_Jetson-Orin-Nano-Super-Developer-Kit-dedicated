---
doc_id: api-http
domain: agentlayer_docs
tags: [api, http]
---

## Overview

AgentLayer exposes an OpenAI-compatible chat endpoint plus app-specific endpoints (workspaces, user data, tools).

This page is a **high-signal index**, not an exhaustive OpenAPI reference.

### Configuration policy

**Runtime and product toggles** (RAG, memory, whether HTTP 5xx responses may include exception text for debugging, etc.) live in **`operator_settings`** and are changed via **Admin → Interfaces** or `PATCH /v1/admin/operator-settings`. Do **not** add new `AGENT_*` environment variables for those — env is for legacy/bootstrap (containers, local dev), not for feature flags.

## Chat (OpenAI-compatible)

- `POST /v1/chat/completions`

Planner loop:
- `src/domain/agent.py::chat_completion`

## Workspaces

- `GET /v1/workspaces` — list workspaces + schema state + kind catalog
- `POST /v1/workspaces` — create new workspace from kind template
- `GET /v1/workspaces/{id}` — load one workspace
- `PATCH /v1/workspaces/{id}` — update title/ui_layout/data
- `DELETE /v1/workspaces/{id}` — delete (owner only)

Sharing:

- `GET /v1/workspaces/{id}/members`
- `POST /v1/workspaces/{id}/members`
- `DELETE /v1/workspaces/{id}/members/{user_id}`

Uploads:

- `POST /v1/workspaces/{id}/files`
- `GET /v1/workspaces/files/{file_id}/content`

Implementation:
- `src/workspace/router.py`

## Tools

- `POST /tools/run` — run one tool call directly (admin/operator flows)
- Registry & policies: `src/domain/plugin_system/tools_api.py`

## User data

Persona/profile/KB sharing:
- `GET /v1/user/persona`
- `PUT /v1/user/persona`

Memory (facts + notes + graph):
- `POST /v1/user/memory/facts/upsert`
- `GET /v1/user/memory/facts`
- `DELETE /v1/user/memory/facts/{key}`
- `POST /v1/user/memory/notes`
- `GET /v1/user/memory/notes/search`
- `DELETE /v1/user/memory/notes/{note_id}`
- `POST /v1/user/memory/graph/nodes` — structured graph node (label, summary, optional `workspace_id`)
- `POST /v1/user/memory/graph/edges` — link two node ids (`src_node_id`, `dst_node_id`)
- `GET /v1/user/memory/graph/nodes`
- `DELETE /v1/user/memory/graph/nodes/{node_id}`
- `GET /v1/user/memory/graph/stats` — counts (nodes, missing embeddings, goal nodes, conflict groups)
- `GET /v1/user/memory/graph/activation-log?limit=100` — recent graph activation events (requires **`memory_graph_log_activations`** in operator settings + migration `schema_019`)
- `POST /v1/user/memory/graph/propose` — body `{ "text": "...", "apply": false, "workspace_id": null }` — LLM proposes nodes/edges; set `apply` true to persist

## RAG (admin)

Requires Bearer for a user with `role=admin`. Ingest/search require **`rag_enabled`** (and related fields) in **`operator_settings`** — **Admin → Interfaces**, not environment variables.

- `POST /v1/admin/rag/ingest`
- `POST /v1/admin/rag/ingest-docs` — batch Markdown under `docs_root` (default repo `docs/`), domain `agentlayer_docs`
- Tool search: `rag_search(...)` (use `domain: "agentlayer_docs"` for ingested product docs)

