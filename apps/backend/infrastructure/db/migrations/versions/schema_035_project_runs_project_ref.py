"""project_runs: add optional project/dashboard reference for UI filtering.

Revision ID: schema_035
Revises: schema_034
"""

from __future__ import annotations

from alembic import op

revision = "schema_035"
down_revision = "schema_034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE project_runs
          ADD COLUMN IF NOT EXISTS dashboard_id UUID REFERENCES user_dashboards(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE project_runs
          ADD COLUMN IF NOT EXISTS project_row_id TEXT;
        """
    )
    op.execute(
        """
        ALTER TABLE project_runs
          ADD COLUMN IF NOT EXISTS project_title TEXT;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_project_runs_dashboard
          ON project_runs (dashboard_id, created_at DESC)
          WHERE dashboard_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_project_runs_project_row
          ON project_runs (dashboard_id, project_row_id, created_at DESC)
          WHERE dashboard_id IS NOT NULL AND project_row_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_project_runs_project_row;")
    op.execute("DROP INDEX IF EXISTS idx_project_runs_dashboard;")
    op.execute("ALTER TABLE project_runs DROP COLUMN IF EXISTS project_title;")
    op.execute("ALTER TABLE project_runs DROP COLUMN IF EXISTS project_row_id;")
    op.execute("ALTER TABLE project_runs DROP COLUMN IF EXISTS dashboard_id;")

