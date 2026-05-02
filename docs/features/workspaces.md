---
doc_id: feature-dashboards
domain: agentlayer_docs
tags: [dashboards, ui, sharing]
---

## What it is

Dashboards are generic dashboards stored as:

- `ui_layout` (blocks + grid positions)
- `data` (JSON payload for blocks)
- `kind` (template kind)
- sharing/access (`access_role`)

Backend stores them in `user_dashboards` (created by `dashboard/**/migrations/001_user_dashboards.sql`).

## Backend

- Router: `src/dashboard/router.py`
- CRUD: `src/dashboard/db.py`
- Template discovery: `src/dashboard/bundle.py`

### Sharing roles

- `owner`: full control, can delete
- `co_owner`: can edit content + manage members (cannot delete)
- `editor`: can edit content
- `viewer`: read-only

Sharing UI is in `interfaces/agent-ui/src/pages/DashboardPage.tsx` (Settings drawer).

## Frontend

- Page: `interfaces/agent-ui/src/pages/DashboardPage.tsx`
- Grid: `interfaces/agent-ui/src/features/dashboard/DashboardGridCanvas.tsx`
- Block renderer: `interfaces/agent-ui/src/features/dashboard/DashboardBlocks.tsx`

## Block types (current)

Examples (not exhaustive):

- `table`
- `markdown`
- `rich_markdown`
- `gallery`
- `hero`
- `timeline`
- `stat` (KPI)
- `chart`
- `sparkline`
- `kanban`
- `embed` (iframe allowlist, e.g. Google Calendar)

## Data paths

Blocks read/write data via `dataPath`.

Supported:

- top-level keys (e.g. `pets`, `items`)
- dotted paths for nested structures (e.g. `albums.0.photos`)

Helper functions:

- `interfaces/agent-ui/src/features/dashboard/dashboardDataPaths.ts` (`getPath`, `setPath`)

## Agent tools (dashboard id)

For built-in kinds with dedicated tools (`pets`, `ideas`, `shopping_list`), `dashboard_id` may be **omitted** when the user has exactly **one** dashboard of that `kind`; the server picks it automatically. If there are several, the tool returns a short list of `id` + `title` so the model can ask or pass the UUID. Logic: `src/dashboard/tool_dashboard_resolve.py`.

## Terminology: dashboard vs project path

In AgentLayer, a **dashboard** is a UI dashboard/board stored in `user_dashboards` (identified by `dashboard_id`).

When scheduling IDE/Git jobs, use **`project_path`** for the local filesystem path to a repository/project folder. Do not call this a "dashboard path" to avoid confusion with UI dashboards.

## Block: schedules

The `schedules` block shows persisted user-defined schedules from `scheduler_jobs` (admin only).

Example block props:

- `scope`: `"dashboard"` | `"global"` | `"both"` (default `"dashboard"`)
- `executionTarget`: `"ide_agent"` | `"server_periodic"` | `"all"` (default `"all"`)

## Files / uploads

Uploads produce a `wsfile:<uuid>` reference.

- Upload endpoint: `POST /v1/dashboards/{dashboard_id}/files`
- Content fetch: `GET /v1/dashboards/files/{id}/content`

Frontend renders `wsfile:` via:

- `interfaces/agent-ui/src/features/dashboard/DashboardBlocks.tsx` (`GalleryImage`)

