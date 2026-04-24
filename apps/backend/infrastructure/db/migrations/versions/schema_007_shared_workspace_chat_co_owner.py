"""Shared workspace chat (one thread per workspace) + co_owner member role.

Revision ID: schema_007
Revises: schema_006
"""

from __future__ import annotations

from alembic import op

revision = "schema_007"
down_revision = "schema_006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS workspace_members_role_check;
        """
    )
    op.execute(
        """
        ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_role_check
        CHECK (role IN ('viewer', 'editor', 'co_owner'));
        """
    )
    op.execute(
        """
        ALTER TABLE chat_conversations
        ADD COLUMN IF NOT EXISTS shared BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_user_workspace;")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_conv_user_workspace_personal
        ON chat_conversations (user_id, workspace_id)
        WHERE workspace_id IS NOT NULL AND shared = false;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_conv_workspace_shared
        ON chat_conversations (workspace_id)
        WHERE workspace_id IS NOT NULL AND shared = true;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_workspace_shared;")
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_user_workspace_personal;")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_chat_conv_user_workspace
        ON chat_conversations (user_id, workspace_id)
        WHERE workspace_id IS NOT NULL;
        """
    )
    op.execute("ALTER TABLE chat_conversations DROP COLUMN IF EXISTS shared;")
    op.execute(
        """
        ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS workspace_members_role_check;
        """
    )
    op.execute(
        """
        ALTER TABLE workspace_members ADD CONSTRAINT workspace_members_role_check
        CHECK (role IN ('viewer', 'editor'));
        """
    )