---
doc_id: runbook-troubleshooting
domain: agentlayer_docs
tags: [runbook, troubleshooting]
---

## RAG returns nothing

**Checks**

- **`rag_enabled`** on in **Admin → Interfaces** (`operator_settings`)
- Docs ingested via `POST /v1/admin/rag/ingest` or batch `POST /v1/admin/rag/ingest-docs`
- **`rag_embedding_dim`** matches the DB column (e.g. `vector(768)`) and the Ollama embedding model output

## Discord gateway DNS failures

**Symptom**

- `Temporary failure in name resolution` for `gateway.discord.gg`

**Cause**

- Container/host DNS instability

**Fix**

- Fix Docker DNS / resolv.conf / network; retry worker

## Workspace uploads not visible

**Checks**

- `workspace_files` table exists (migration)
- upload dir configured and writable
- `wsfile:` URLs rendered in `WorkspaceBlocks.tsx` (`GalleryImage`)

