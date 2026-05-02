"""Observability: log which graph nodes were activated per chat turn (hashed query, scores in JSON).

Revision ID: schema_019
Revises: schema_018
"""

from __future__ import annotations

from alembic import op

revision = "schema_019"
down_revision = "schema_018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memory_graph_activation_log (
          id BIGSERIAL PRIMARY KEY,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          dashboard_id UUID NULL REFERENCES user_dashboards(id) ON DELETE SET NULL,
          node_ids BIGINT[] NOT NULL DEFAULT '{}',
          query_sha256 CHAR(64) NULL,
          meta JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_graph_activation_user_created
          ON user_memory_graph_activation_log (tenant_id, user_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_memory_graph_activation_log;")
