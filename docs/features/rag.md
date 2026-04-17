---
doc_id: feature-rag
domain: agentlayer_docs
tags: [rag, pgvector, embeddings]
---

## What it is

RAG provides **semantic search** over ingested documents using:

- Postgres + `pgvector`
- embeddings from Ollama (`/api/embed` with fallback to `/api/embeddings`)

By default, vectors are scoped to **tenant + user** (private notes and uploads stay per user).

The domain **`agentlayer_docs`** is **tenant-wide**: after an admin ingests documentation, every user in that tenant can retrieve the same chunks with `rag_search(..., domain="agentlayer_docs")`. Configure the allowlist with `AGENT_RAG_TENANT_SHARED_DOMAINS` (comma-separated; unset defaults to `agentlayer_docs`; set to empty to disable tenant-wide domains).

## Where it lives

- Service: `src/api/rag.py`
- API router: `src/api/rag_api.py`
- Tool: `tools/agent/knowledge/rag/rag.py` (search only)
- Tables: `rag_documents`, `rag_chunks` (`src/infrastructure/db/migrations/sql/schema.sql`)

## Config

In `src/core/config.py`:

- `AGENT_RAG_ENABLED`
- `AGENT_RAG_OLLAMA_MODEL`
- `AGENT_RAG_EMBEDDING_DIM` (must match DB column `vector(768)` by default)
- `AGENT_RAG_TOP_K`
- `AGENT_RAG_TENANT_SHARED_DOMAINS` — domains searched without per-user filter
- `AGENT_DOCS_ROOT` — optional filesystem override for markdown ingest (default: `<repo>/docs`)

## Ingest (admin HTTP)

Both routes require a Bearer token for a user with **`role=admin`**:

- `POST /v1/admin/rag/ingest` — body: `text`, optional `domain`, `title`, `source_uri`
- `POST /v1/admin/rag/ingest-docs` — optional JSON: `docs_root`, `domain` (default `agentlayer_docs`), `purge_first` (default `true`). Walks `*.md` under `docs_root`, embeds each file, and (when purging) removes prior rows for that **tenant + domain** so reindex stays clean.

CLI helper (stdlib HTTP only):

- `scripts/reindex_agentlayer_docs.py` — uses `AGENT_BASE_URL`, `AGENT_ADMIN_TOKEN`, optional `AGENT_INGEST_DOCS_JSON`

On each API process start, the server **attempts** to re-ingest all `docs/**/*.md` into domain `agentlayer_docs` (purge tenant rows for that domain first), using the oldest admin user as row owner, when a docs directory exists. If the embedding stack is not configured or Ollama is unreachable, that pass is skipped or logged and the API still starts.

Recommended `domain` values:

- `agentlayer_docs` (repo docs, tenant-visible)
- `user_uploads`
- `manual_notes`

## Search

Tool:

- `rag_search({ query, domain?, limit? })`

Use `domain: "agentlayer_docs"` when answering questions about AgentLayer product behavior from ingested markdown.

## Troubleshooting

- If you see embedding dim mismatch: check `AGENT_RAG_EMBEDDING_DIM` and DB vector column size.
- If search returns nothing: ensure ingest happened, `AGENT_RAG_ENABLED=true`, and Ollama serves the configured embedding model.
- If `ingest-docs` reports missing directory: mount or copy `docs/` into the container, or set `AGENT_DOCS_ROOT` / request body `docs_root`.
