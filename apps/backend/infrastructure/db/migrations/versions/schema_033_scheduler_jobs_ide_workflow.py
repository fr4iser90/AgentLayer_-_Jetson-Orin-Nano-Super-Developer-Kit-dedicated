"""scheduler_jobs: ide_workflow JSON (new chat, preamble, optional git).

Revision ID: schema_033
Revises: schema_032
"""

from __future__ import annotations

from alembic import op

revision = "schema_033"
down_revision = "schema_032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE scheduler_jobs
          ADD COLUMN IF NOT EXISTS ide_workflow JSONB NOT NULL DEFAULT '{}'::jsonb;
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN scheduler_jobs.ide_workflow IS
          'Optional workflow for ide_agent: new_chat, prompt_preamble, git_repo_path, git_branch_template, git_source_branch.';
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE scheduler_jobs DROP COLUMN IF EXISTS ide_workflow;")
