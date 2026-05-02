"""dashboard_members: share dashboards (viewer/editor) within tenant.

Revision ID: schema_005
Revises: schema_004
"""

from __future__ import annotations

from alembic import op

revision = "schema_005"
down_revision = "schema_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_members (
          dashboard_id UUID NOT NULL,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          role TEXT NOT NULL CHECK (role IN ('viewer', 'editor')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (dashboard_id, user_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dashboard_members_user "
        "ON dashboard_members (user_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dashboard_members_user;")
    op.execute("DROP TABLE IF EXISTS dashboard_members;")
