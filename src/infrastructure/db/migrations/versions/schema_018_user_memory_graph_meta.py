"""Graph nodes: confidence, source, verification, subject_key (conflicts), stability (decay), priority (goals).

Revision ID: schema_018
Revises: schema_017
"""

from __future__ import annotations

from alembic import op

revision = "schema_018"
down_revision = "schema_017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_memory_graph_nodes
          ADD COLUMN IF NOT EXISTS confidence REAL NOT NULL DEFAULT 1.0;
        """
    )
    op.execute(
        """
        ALTER TABLE user_memory_graph_nodes
          ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'user';
        """
    )
    op.execute(
        """
        ALTER TABLE user_memory_graph_nodes
          ADD COLUMN IF NOT EXISTS last_verified TIMESTAMPTZ NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE user_memory_graph_nodes
          ADD COLUMN IF NOT EXISTS subject_key TEXT NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE user_memory_graph_nodes
          ADD COLUMN IF NOT EXISTS stability TEXT NOT NULL DEFAULT 'normal';
        """
    )
    op.execute(
        """
        ALTER TABLE user_memory_graph_nodes
          ADD COLUMN IF NOT EXISTS priority REAL NOT NULL DEFAULT 0;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_graph_nodes_subject
          ON user_memory_graph_nodes (tenant_id, user_id, subject_key)
          WHERE deleted_at IS NULL AND subject_key IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_user_memory_graph_nodes_subject;")
    for col in (
        "priority",
        "stability",
        "subject_key",
        "last_verified",
        "source",
        "confidence",
    ):
        op.execute(f"ALTER TABLE user_memory_graph_nodes DROP COLUMN IF EXISTS {col};")
