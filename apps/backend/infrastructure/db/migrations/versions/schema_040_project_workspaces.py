"""project_workspaces — user Git project workspaces for coding agent.

Revision ID: schema_040
Revises: schema_039
"""

from __future__ import annotations

from alembic import op

revision = "schema_040"
down_revision = "schema_039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS project_workspaces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            path TEXT NOT NULL,
            source VARCHAR(32) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'git')),
            git_url TEXT,
            git_branch VARCHAR(255) DEFAULT 'main',
            access_role VARCHAR(16) NOT NULL DEFAULT 'owner' CHECK (access_role IN ('owner', 'editor', 'viewer')),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(owner_user_id, name)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_project_workspaces_owner ON project_workspaces(owner_user_id);
        """
    )
    op.execute(
        """
        COMMENT ON TABLE project_workspaces IS
          'User Git project workspaces for coding agent (separate from dashboards).';
        """
    )
    op.execute(
        """
        ALTER TABLE users
          ADD COLUMN IF NOT EXISTS workspace_quota INTEGER NOT NULL DEFAULT 10;
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN users.workspace_quota IS
          'Max workspaces this user may create.';
        """
    )
    op.execute(
        """
        ALTER TABLE users
          ADD COLUMN IF NOT EXISTS workspace_self_allowed BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN users.workspace_self_allowed IS
          'User may access the AgentLayer self-editing workspace.';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_workspaces;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS workspace_quota;")