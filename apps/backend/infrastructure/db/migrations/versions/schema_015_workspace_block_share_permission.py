"""Granular block shares: view (read-only) vs edit (data + allowed blocks).

Revision ID: schema_015
Revises: schema_014
"""

from __future__ import annotations

from alembic import op

revision = "schema_015"
down_revision = "schema_014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE workspace_block_share_grants
          ADD COLUMN IF NOT EXISTS permission TEXT NOT NULL DEFAULT 'view';
        """
    )
    op.execute(
        """
        UPDATE workspace_block_share_grants SET permission = 'view'
        WHERE permission IS NULL OR btrim(permission) = '';
        """
    )
    op.execute(
        """
        ALTER TABLE workspace_block_share_grants
          DROP CONSTRAINT IF EXISTS workspace_block_share_grants_permission_check;
        """
    )
    op.execute(
        """
        ALTER TABLE workspace_block_share_grants
          ADD CONSTRAINT workspace_block_share_grants_permission_check
          CHECK (permission IN ('view', 'edit'));
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE workspace_block_share_grants DROP CONSTRAINT IF EXISTS workspace_block_share_grants_permission_check;"
    )
    op.execute(
        "ALTER TABLE workspace_block_share_grants DROP COLUMN IF EXISTS permission;"
    )
