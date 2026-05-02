"""Structured memory graph (nodes + edges) for compact activated context (FMA-style MVP).

Revision ID: schema_016
Revises: schema_015
"""

from __future__ import annotations

from alembic import op

revision = "schema_016"
down_revision = "schema_015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memory_graph_nodes (
          id BIGSERIAL PRIMARY KEY,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          dashboard_id UUID NULL REFERENCES user_dashboards(id) ON DELETE CASCADE,
          kind TEXT NOT NULL DEFAULT 'event',
          label TEXT NOT NULL,
          summary TEXT NOT NULL DEFAULT '',
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          importance REAL NOT NULL DEFAULT 1.0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at TIMESTAMPTZ NULL
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_graph_nodes_scope_updated
          ON user_memory_graph_nodes (tenant_id, user_id, dashboard_id, updated_at DESC)
          WHERE deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memory_graph_edges (
          id BIGSERIAL PRIMARY KEY,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          src_node_id BIGINT NOT NULL REFERENCES user_memory_graph_nodes(id) ON DELETE CASCADE,
          dst_node_id BIGINT NOT NULL REFERENCES user_memory_graph_nodes(id) ON DELETE CASCADE,
          rel_type TEXT NOT NULL DEFAULT 'related',
          weight REAL NOT NULL DEFAULT 1.0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT ck_user_memory_graph_edges_no_self CHECK (src_node_id <> dst_node_id),
          CONSTRAINT ux_user_memory_graph_edges_unique UNIQUE (src_node_id, dst_node_id, rel_type)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_graph_edges_src
          ON user_memory_graph_edges (tenant_id, user_id, src_node_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_memory_graph_edges_dst
          ON user_memory_graph_edges (tenant_id, user_id, dst_node_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_memory_graph_edges;")
    op.execute("DROP TABLE IF EXISTS user_memory_graph_nodes;")
