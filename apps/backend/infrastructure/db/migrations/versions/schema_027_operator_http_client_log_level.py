"""httpx/httpcore log level in operator_settings (Admin → Interfaces).

Revision ID: schema_027
Revises: schema_026
"""

from __future__ import annotations

from alembic import op

revision = "schema_027"
down_revision = "schema_026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS http_client_log_level TEXT NOT NULL DEFAULT 'WARNING';
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN operator_settings.http_client_log_level IS
          'Logging level for httpx/httpcore (WARNING = quiet long-poll; INFO = per-request).';
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE operator_settings DROP COLUMN IF EXISTS http_client_log_level;"
    )
