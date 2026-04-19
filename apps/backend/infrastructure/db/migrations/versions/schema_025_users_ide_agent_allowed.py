"""users.ide_agent_allowed — non-admin access to IDE Agent when operator enables PIDEA.

Revision ID: schema_025
Revises: schema_024
"""

from __future__ import annotations

from alembic import op

revision = "schema_025"
down_revision = "schema_024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
          ADD COLUMN IF NOT EXISTS ide_agent_allowed BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN users.ide_agent_allowed IS
          'When operator PIDEA is on: non-admins with true may use IDE Agent; admins always may.';
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS ide_agent_allowed;")
