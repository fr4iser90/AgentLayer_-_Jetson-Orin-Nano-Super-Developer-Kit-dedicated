"""HTTP error detail: optional exception text via operator_settings (not env).

Revision ID: schema_026
Revises: schema_025
"""

from __future__ import annotations

from alembic import op

revision = "schema_026"
down_revision = "schema_025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS expose_internal_errors BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN operator_settings.expose_internal_errors IS
          'When true, some HTTP 5xx responses may include str(exception) for debugging; default false.';
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE operator_settings DROP COLUMN IF EXISTS expose_internal_errors;"
    )
