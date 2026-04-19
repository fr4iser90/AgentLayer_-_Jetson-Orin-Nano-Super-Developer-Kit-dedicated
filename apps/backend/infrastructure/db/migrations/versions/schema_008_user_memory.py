"""User memory: facts + semantic notes (pgvector).

Revision ID: schema_008
Revises: schema_007
"""

from __future__ import annotations

from alembic import op

revision = "schema_008"
down_revision = "schema_007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Facts: structured key/value (JSONB), optionally scoped to a workspace.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memory_facts (
          id BIGSERIAL PRIMARY KEY,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          workspace_id UUID NULL REFERENCES user_workspaces(id) ON DELETE CASCADE,
          key TEXT NOT NULL,
          value_json JSONB NOT NULL,
          confidence REAL NOT NULL DEFAULT 1.0,
          source TEXT NOT NULL DEFAULT 'user',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          expires_at TIMESTAMPTZ NULL,
          deleted_at TIMESTAMPTZ NULL
        );
        """
    )
    # Unique facts per scope (global vs workspace) while allowing soft-delete.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_user_memory_facts_global_key
          ON user_memory_facts (tenant_id, user_id, key)
          WHERE workspace_id IS NULL AND deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_user_memory_facts_workspace_key
          ON user_memory_facts (tenant_id, user_id, workspace_id, key)
          WHERE workspace_id IS NOT NULL AND deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_facts_scope_updated
          ON user_memory_facts (tenant_id, user_id, workspace_id, updated_at DESC)
          WHERE deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_facts_scope_expires
          ON user_memory_facts (tenant_id, user_id, workspace_id, expires_at)
          WHERE deleted_at IS NULL;
        """
    )

    # Notes: semantic memory with embeddings (pgvector). Requires extension vector.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memory_notes (
          id BIGSERIAL PRIMARY KEY,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          workspace_id UUID NULL REFERENCES user_workspaces(id) ON DELETE CASCADE,
          text TEXT NOT NULL,
          tags TEXT[] NOT NULL DEFAULT '{}',
          source TEXT NOT NULL DEFAULT 'user',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at TIMESTAMPTZ NULL,
          embedding vector(768) NOT NULL
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_notes_scope_updated
          ON user_memory_notes (tenant_id, user_id, workspace_id, updated_at DESC)
          WHERE deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_notes_embedding
          ON user_memory_notes USING hnsw (embedding vector_cosine_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_user_memory_notes_embedding;")
    op.execute("DROP INDEX IF EXISTS idx_user_memory_notes_scope_updated;")
    op.execute("DROP TABLE IF EXISTS user_memory_notes;")

    op.execute("DROP INDEX IF EXISTS idx_user_memory_facts_scope_expires;")
    op.execute("DROP INDEX IF EXISTS idx_user_memory_facts_scope_updated;")
    op.execute("DROP INDEX IF EXISTS ux_user_memory_facts_workspace_key;")
    op.execute("DROP INDEX IF EXISTS ux_user_memory_facts_global_key;")
    op.execute("DROP TABLE IF EXISTS user_memory_facts;")

