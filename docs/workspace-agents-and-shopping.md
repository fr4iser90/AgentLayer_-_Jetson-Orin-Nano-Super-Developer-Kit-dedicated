# Workspace agents, shopping lists, and automation

This document describes how **workspaces**, **agent tools**, **scheduled jobs**, and future **RAG** fit together in AgentLayer, and how the **shopping list** vertical is intended to evolve.

## Layers (mental model)

| Layer | Role |
|--------|------|
| **Workspace UI** | Declarative blocks (table, markdown, …) driven by `ui_layout` and JSON `data` in `user_workspaces` (see bundles under `workspace/<kind>/`). |
| **Workspace HTTP API** | `GET/PATCH /v1/workspaces/...` — CRUD for `title`, `ui_layout`, `data`; access via owner and `workspace_members`. |
| **Agent tools** | Python modules under `tools/` loaded by the registry; chat (web, WebSocket) and Discord use the same `chat_completion` pipeline. Tools call DB/workspace helpers with `get_identity()` for tenant and user. |
| **Scheduled jobs** | **Not** LLM tools: Python modules that expose `HANDLERS` + `RUN_EVERY_MINUTES` are picked up by `scheduled_job_registry` and run on an interval in `cron.py`. User-editable schedules from the UI are a possible future step. |
| **RAG / embeddings** | Not workspace-scoped by default today. A dedicated design would attach chunks and retrieval to `workspace_id` (or files under workspace storage). |

## Workspace-specific “agents”

There is no separate agent process per workspace. What you can do today:

1. **Narrow tools** — HTTP header `X-Agent-Tool-Domain` or body `TOOL_DOMAIN` restricts which tools are sent to the model (see tool registry and `TOOL_DOMAIN` on modules).
2. **Strong tool descriptions** — Shopping-related tools should state that they require a `workspace_id` and how to obtain it (list workspaces first).
3. **Optional UI context (implemented)** — Chat requests may include `agent_workspace_context: { "workspace_id": "<uuid>" }`. The server loads that workspace with the current user’s access rights and appends a `[Workspace context]` line to the system prompt (title, kind, role). The web app sends this when you open **Chat** from a workspace (`/app/chat?workspace=<uuid>` or **“Chat with this workspace”** on the workspace page). If the id is inaccessible, the prompt says so and the model must not assume an id.

## Shopping list (`kind: shopping_list`)

### Data model

- Template: `workspace/shopping-list/shopping-list.template.json`.
- Stored `data` shape: `items` (array of rows) and `notes` (markdown string for the notes block).
- Row fields align with the table block: `checked`, `name`, `qty`, `store` (see template `columns`).

### Agent tools (implemented)

Module: `tools/agent/productivity/shopping_list/shopping_list.py`

- **`shopping_list_workspaces`** — Lists workspaces the user can access with `kind === "shopping_list"` (id + title). Use this when the user did not specify which list.
- **`shopping_list_read`** — Returns `title`, `items`, and `notes` for one workspace (must be `shopping_list`).
- **`shopping_list_add_items`** — Appends one or more rows to `data.items` (editor/owner only).

All operations require an authenticated user (same as other identity-bound tools).

### Discord and web chat

The Discord bridge calls the same completion path as the web app. Once the model selects the shopping tools, behavior is consistent across channels.

### Cron, prices, stores, favorites (roadmap)

**Product goals (target experience — not all built yet):**

- Natural language from **web chat or Discord** to add lines to the shopping list (same agent pipeline).
- Optional **scheduled job** (e.g. early morning) that refreshes **price / offer** information according to user rules.
- **Store and brand preferences** (e.g. only certain chains or brands), optional **discount** awareness, and optional **third-party price tracking** (e.g. large retailers) — each needs an explicit, compliant data source and/or dedicated tools; nothing is implied by the list-only tools above.

Background price checks, store filters (e.g. only REWE), or Amazon tracking are **not** implemented in the core tools in § “Agent tools (implemented)”. A realistic implementation path:

1. Store **preferences** (favorite chains, brands) in `data` (e.g. `data.preferences`) or a future normalized table.
2. Add a **scheduled job module** that reads those preferences and writes results into `notes` or a dedicated `data.price_log` structure.
3. Integrate **external data** carefully (APIs, manual CSV, or compliant scraping) — product and legal constraints vary by region.

See also `workspace/PLAN_TASKS_PHASE_2_3.md` for task/workspace alignment options and `workspace/PLAN_PLUG_AND_PLAY.md` for broader plug-and-play goals.

## Related code

- Workspace DB: `src/workspace/db.py`
- Workspace HTTP: `src/workspace/router.py`
- Scheduled jobs: `src/domain/plugin_system/scheduled_job_registry.py`, `src/infrastructure/cron.py`
- Tool registry: `src/domain/plugin_system/registry.py`
- ADR: `docs/adr/0001-tool-and-agent-architecture.md`
