"""dashboard_files + operator upload limits (global overrides).

Revision ID: schema_004
Revises: schema_003
"""

from __future__ import annotations

from alembic import op

revision = "schema_004"
down_revision = "schema_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS "
        "dashboard_upload_max_file_mb INTEGER;"
    )
    op.execute(
        "ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS "
        "dashboard_upload_allowed_mime TEXT;"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_files (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          dashboard_id UUID NOT NULL,
          storage_relpath TEXT NOT NULL UNIQUE,
          content_type TEXT NOT NULL,
          size_bytes BIGINT NOT NULL,
          original_name TEXT NOT NULL DEFAULT '',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dashboard_files_owner "
        "ON dashboard_files (owner_user_id, created_at DESC);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_dashboard_files_dashboard "
        "ON dashboard_files (dashboard_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dashboard_files_dashboard;")
    op.execute("DROP INDEX IF EXISTS idx_dashboard_files_owner;")
    op.execute("DROP TABLE IF EXISTS dashboard_files;")
    op.execute(
        "ALTER TABLE operator_settings DROP COLUMN IF EXISTS dashboard_upload_allowed_mime;"
    )
    op.execute(
        "ALTER TABLE operator_settings DROP COLUMN IF EXISTS dashboard_upload_max_file_mb;"
    )
