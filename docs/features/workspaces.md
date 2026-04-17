---
doc_id: feature-workspaces
domain: agentlayer_docs
tags: [workspaces, ui, sharing]
---

## What it is

Workspaces are generic dashboards stored as:

- `ui_layout` (blocks + grid positions)
- `data` (JSON payload for blocks)
- `kind` (template kind)
- sharing/access (`access_role`)

Backend stores them in `user_workspaces` (created by `workspace/**/migrations/001_user_workspaces.sql`).

## Backend

- Router: `src/workspace/router.py`
- CRUD: `src/workspace/db.py`
- Template discovery: `src/workspace/bundle.py`

### Sharing roles

- `owner`: full control, can delete
- `co_owner`: can edit content + manage members (cannot delete)
- `editor`: can edit content
- `viewer`: read-only

Sharing UI is in `interfaces/agent-ui/src/pages/WorkspacePage.tsx` (Settings drawer).

## Frontend

- Page: `interfaces/agent-ui/src/pages/WorkspacePage.tsx`
- Grid: `interfaces/agent-ui/src/features/workspace/WorkspaceGridCanvas.tsx`
- Block renderer: `interfaces/agent-ui/src/features/workspace/WorkspaceBlocks.tsx`

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

- `interfaces/agent-ui/src/features/workspace/workspaceDataPaths.ts` (`getPath`, `setPath`)

## Agent tools (workspace id)

For built-in kinds with dedicated tools (`pets`, `ideas`, `shopping_list`), `workspace_id` may be **omitted** when the user has exactly **one** workspace of that `kind`; the server picks it automatically. If there are several, the tool returns a short list of `id` + `title` so the model can ask or pass the UUID. Logic: `src/workspace/tool_workspace_resolve.py`.

## Files / uploads

Uploads produce a `wsfile:<uuid>` reference.

- Upload endpoint: `POST /v1/workspaces/{workspace_id}/files`
- Content fetch: `GET /v1/workspaces/files/{id}/content`

Frontend renders `wsfile:` via:

- `interfaces/agent-ui/src/features/workspace/WorkspaceBlocks.tsx` (`GalleryImage`)

