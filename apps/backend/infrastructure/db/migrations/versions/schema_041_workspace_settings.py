"""Add workspace_allow_self_editing to operator_settings and workspace_self_allowed to users.

Revision ID: schema_041
Revises: schema_040
"""

from __future__ import annotations

from alembic import op

revision = "schema_041"
down_revision = "schema_040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS workspace_allow_self_editing BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute(
        """
        ALTER TABLE users
          ADD COLUMN IF NOT EXISTS workspace_self_allowed BOOLEAN NOT NULL DEFAULT false;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS workspace_allow_self_editing;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS workspace_self_allowed;")