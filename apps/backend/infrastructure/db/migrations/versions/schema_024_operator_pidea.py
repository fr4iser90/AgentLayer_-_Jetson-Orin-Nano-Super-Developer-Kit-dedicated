"""PIDEA (DOM / Cursor CDP) flags and overrides in operator_settings.

Revision ID: schema_024
Revises: schema_023
"""

from __future__ import annotations

from alembic import op

revision = "schema_024"
down_revision = "schema_023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS pidea_enabled BOOLEAN NOT NULL DEFAULT false,
          ADD COLUMN IF NOT EXISTS pidea_cdp_http_url TEXT,
          ADD COLUMN IF NOT EXISTS pidea_selector_ide TEXT,
          ADD COLUMN IF NOT EXISTS pidea_selector_version TEXT;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          DROP COLUMN IF EXISTS pidea_enabled,
          DROP COLUMN IF EXISTS pidea_cdp_http_url,
          DROP COLUMN IF EXISTS pidea_selector_ide,
          DROP COLUMN IF EXISTS pidea_selector_version;
        """
    )
