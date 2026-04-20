"""project_runs: add optional project/workspace reference for UI filtering.

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
          ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES user_workspaces(id) ON DELETE SET NULL;
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
        CREATE INDEX IF NOT EXISTS idx_project_runs_workspace
          ON project_runs (workspace_id, created_at DESC)
          WHERE workspace_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_project_runs_project_row
          ON project_runs (workspace_id, project_row_id, created_at DESC)
          WHERE workspace_id IS NOT NULL AND project_row_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_project_runs_project_row;")
    op.execute("DROP INDEX IF EXISTS idx_project_runs_workspace;")
    op.execute("ALTER TABLE project_runs DROP COLUMN IF EXISTS project_title;")
    op.execute("ALTER TABLE project_runs DROP COLUMN IF EXISTS project_row_id;")
    op.execute("ALTER TABLE project_runs DROP COLUMN IF EXISTS workspace_id;")

