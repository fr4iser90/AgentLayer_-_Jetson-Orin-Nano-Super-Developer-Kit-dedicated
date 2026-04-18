---
doc_id: feature-memory
domain: agentlayer_docs
tags: [memory, privacy, rag]
---

## What it is

Memory is **opt-in persistent storage** for user preferences and personal context.

It has two layers:

1. **Facts**: structured key/value JSON (authoritative)
2. **Notes**: free-form semantic notes (pgvector + embeddings)

The model does not “own” memory: all data lives in Postgres, and retrieval is injected into the system message.

## Where it lives

- Tables:
  - `user_memory_facts`
  - `user_memory_notes`
- Migration:
  - `src/infrastructure/db/migrations/versions/schema_008_user_memory.py`
- DB functions:
  - `src/infrastructure/db/db.py` (`memory_fact_*`, `memory_note_*`)
- Service:
  - `src/api/memory.py`
- Tool:
  - `tools/agent/knowledge/memory/memory.py`
- Injection into chat:
  - `src/domain/agent.py` (`_inject_user_memory_context`)

## Opt-in writes (privacy)

Only store memory when the user explicitly asks (e.g. “remember …” / “merk dir …”).

Secrets are rejected (token/password/key-like patterns).

## Enabling (operators)

Do **not** rely on container environment variables for day-to-day configuration — that path is legacy and easy to get wrong.

- **Agent tools**: In the Web UI, open **Admin → Tools**, find the **memory** package under **Knowledge & memory**, and enable or disable it (plus role / tenant restrictions) like any other tool package. That controls whether chat requests expose the `memory_*` tool definitions to the model.
- **REST**: Authenticated users can also manage facts and notes via `POST/GET/DELETE /v1/user/memory/...` (see `docs/api/http.md`) when the deployment exposes that API.

## Scoping

Memory can be:

- global per user (`workspace_id = NULL`)
- workspace-scoped (`workspace_id = <uuid>`)

Workspace-scoped facts override global facts when keys conflict.

## Contracts

### Fact

- key: string (e.g. `language`, `preferred_answer_length`)
- value_json: JSON (typed)
- expires_at: optional ISO timestamp (auto filtered on retrieval)

### Note

- text: string
- tags: string[]
- embedding: computed via Ollama embeddings (same dim as RAG, typically 768)

## Example usage (tool calls)

Structured preference:

```json
{ "key": "preferred_output_language", "value_json": "de" }
```

Semantic note:

```json
{ "text": "User builds a homelab with multiple Jetson nodes and a Discord agent tool system.", "tags": ["homelab", "discord"] }
```

