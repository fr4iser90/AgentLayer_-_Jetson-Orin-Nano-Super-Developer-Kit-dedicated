"""scheduler_jobs: soft delete / archive via deleted_at.

Revision ID: schema_036
Revises: schema_035
"""

from __future__ import annotations

from alembic import op

revision = "schema_036"
down_revision = "schema_035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE scheduler_jobs
          ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_tenant_deleted
          ON scheduler_jobs (tenant_id, deleted_at)
          WHERE deleted_at IS NOT NULL;
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN scheduler_jobs.deleted_at IS
          'Soft delete / archive timestamp. Archived jobs are excluded from lists by default.';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_scheduler_jobs_tenant_deleted;")
    op.execute("ALTER TABLE scheduler_jobs DROP COLUMN IF EXISTS deleted_at;")

