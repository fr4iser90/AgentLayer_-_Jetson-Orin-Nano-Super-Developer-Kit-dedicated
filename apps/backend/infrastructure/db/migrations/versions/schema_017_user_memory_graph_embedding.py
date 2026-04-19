"""Graph memory nodes: pgvector embedding for semantic activation (hybrid with keyword match).

Revision ID: schema_017
Revises: schema_016
"""

from __future__ import annotations

from alembic import op

revision = "schema_017"
down_revision = "schema_016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_memory_graph_nodes
          ADD COLUMN IF NOT EXISTS embedding vector(768);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_graph_nodes_embedding
          ON user_memory_graph_nodes USING hnsw (embedding vector_cosine_ops)
          WHERE deleted_at IS NULL AND embedding IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_user_memory_graph_nodes_embedding;")
    op.execute("ALTER TABLE user_memory_graph_nodes DROP COLUMN IF EXISTS embedding;")
