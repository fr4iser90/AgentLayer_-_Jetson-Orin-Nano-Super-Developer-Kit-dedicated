"""project_runs: one-shot execution queue (decoupled from scheduler).

Revision ID: schema_034
Revises: schema_033
"""

from __future__ import annotations

from alembic import op

revision = "schema_034"
down_revision = "schema_033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_runs (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          created_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          execution_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

          -- Optional linkage back to a schedule. NULL when created manually ("Run now").
          scheduler_job_id UUID NULL REFERENCES scheduler_jobs(id) ON DELETE SET NULL,

          -- Minimal payload for execution (kept flexible).
          execution_target TEXT NOT NULL CHECK (execution_target IN ('ide_agent')),
          instructions TEXT NOT NULL,
          ide_workflow JSONB NOT NULL DEFAULT '{}'::jsonb,

          status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled'))
            DEFAULT 'queued',
          error TEXT NULL,

          started_at TIMESTAMPTZ NULL,
          finished_at TIMESTAMPTZ NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_project_runs_tenant_status_created
          ON project_runs (tenant_id, status, created_at ASC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_project_runs_scheduler_job
          ON project_runs (scheduler_job_id)
          WHERE scheduler_job_id IS NOT NULL;
        """
    )
    op.execute(
        """
        COMMENT ON TABLE project_runs IS
          'One-shot execution queue for IDE agent runs; scheduler enqueues runs, execution worker processes them.';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_runs;")

