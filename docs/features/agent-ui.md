---
doc_id: feature-agent-ui
domain: agentlayer_docs
tags: [agent-ui, workspace, navigation, blocks]
---

## Scope

This page describes the **agent-ui** workspace experience: list and detail editing, hub-based navigation, layout grid, block types, and how workspace JSON maps into the UI.

Primary code: `interfaces/agent-ui/src/pages/WorkspacePage.tsx` and `interfaces/agent-ui/src/features/workspace/`.

## Workspace page layout

`WorkspacePage` loads workspace metadata from `GET /v1/workspaces` (list, kind catalog, schema flags) and `GET/PATCH /v1/workspaces/{id}` for the selected workspace.

The screen splits into:

1. **Left sidebar** — flat list of all workspaces (“Yours & shared”) with role badges, delete affordances for owned rows, and actions to open the **catalog** or create a workspace.
2. **Main column** — either the **hub navigator** + workspace canvas, or the **catalog** / first-time **schema install** flow when no packs are installed.

## Hub navigator

The hub UI groups workspaces into fixed categories for faster switching.

- **Data & rules**: `workspaceHubNav.ts` defines `WorkspaceHubId` (`pets`, `family`, `media`, `home`, `work`, `other`), `DEFAULT_HUBS`, `inferHubId` (kind → hub, then title keyword → hub), and `groupWorkspacesByHub` / `hubForSelectedId`.
- **Component**: `WorkspaceHubNavigator.tsx` — hub pills, in-hub search, keyboard navigation, **favorites** (persisted in `localStorage` under `workspace_nav_favorites_v1`), and a **recents** strip.

`WorkspacePage` keeps `activeHubOverride` so the visible hub can follow keyboard or explicit hub changes while a workspace stays selected.

## Settings drawer

`WorkspaceSettingsDrawer` holds secondary controls (members, danger zone, etc.) opened from the workspace header. Access rules (`viewer` / `editor` / `co_owner` / `owner`) gate editing and member management in the page logic.

## Blocks and `ui_layout`

Workspace content is stored as:

- `data` — arbitrary JSON for the pack (tables, kanban columns, etc.).
- `ui_layout` — `{ version, blocks[] }` where each block has `id`, `type`, `grid` (`x`, `y`, `w`, `h`), and `props` (often `dataPath`, `columns`, titles).

Types live in `features/workspace/types.ts`. Supported `BlockType` values include: `table`, `markdown`, `gallery`, `hero`, `timeline`, `stat`, `chart`, `sparkline`, `kanban`, `rich_markdown`, `embed`.

### Data paths

`workspaceDataPaths.ts` implements `getPath` / `setPath` for dotted paths and numeric array segments (e.g. `albums.0.photos`). Blocks bind to `data` through `props.dataPath`.

### Rendering

- **List-style editing**: `WorkspaceBlocks.tsx` maps each block to `WorkspaceBlockTile` → `BlockView` (tables, markdown, gallery, charts, kanban, embed, etc.).
- **Freeform grid**: `WorkspaceGridCanvas.tsx` uses `react-grid-layout` with `verticalCompactor`, adds blocks with stable `dataPath` prefixes per block family (`BLOCK_PREFIX`), and reuses `WorkspaceBlockTile` inside grid cells.

### Embed allowlist

`EmbedBlock.tsx` exports `EMBED_ALLOWED_HOSTNAMES` and `embedUrlAllowed`: only **https** URLs whose hostname matches the allowlist (or a subdomain of an allowed host) may render in an iframe.

### Charts

`chart/chartRegister.ts` and `chart/ChartBlockViews.tsx` register chart kinds used by `chart` / `sparkline` blocks.

## Embedded chat

`WorkspaceEmbeddedChat.tsx` embeds the chat surface in the workspace context when the layout or product calls for it (same auth stack as the rest of agent-ui).

## Related docs

- Workspace API and packs: `docs/features/workspaces.md`
- RAG (including `agentlayer_docs` ingest): `docs/features/rag.md`
