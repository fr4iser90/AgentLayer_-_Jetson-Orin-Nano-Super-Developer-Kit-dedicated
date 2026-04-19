"""Granular workspace sharing: only selected block ids visible to another user (read-only).

Revision ID: schema_014
Revises: schema_013
"""

from __future__ import annotations

from alembic import op

revision = "schema_014"
down_revision = "schema_013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_block_share_grants (
          workspace_id UUID NOT NULL REFERENCES user_workspaces(id) ON DELETE CASCADE,
          viewer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          block_ids TEXT[] NOT NULL,
          created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (workspace_id, viewer_user_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_block_share_viewer "
        "ON workspace_block_share_grants(viewer_user_id, tenant_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS workspace_block_share_grants;")
