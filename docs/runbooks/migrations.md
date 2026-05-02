---
doc_id: runbook-migrations
domain: agentlayer_docs
tags: [runbook, db, migrations]
---

## Goal

Apply database migrations safely and verify schema state.

## Where migrations live

- Alembic migrations: `src/infrastructure/db/migrations/versions/`
- Schema snapshot: `src/infrastructure/db/migrations/sql/schema.sql`

## Procedure

1. Backup DB (if production).
2. Run Alembic upgrade to head.
3. Verify required tables exist:
   - `user_dashboards`, `dashboard_members`, `chat_conversations`, `rag_documents`, `rag_chunks`, `user_memory_facts`, `user_memory_notes`, etc.

## Common failures

### Missing `vector` extension

Symptom: pgvector table creation fails.  
Fix: ensure `CREATE EXTENSION IF NOT EXISTS vector;` was executed (migration should do this).

