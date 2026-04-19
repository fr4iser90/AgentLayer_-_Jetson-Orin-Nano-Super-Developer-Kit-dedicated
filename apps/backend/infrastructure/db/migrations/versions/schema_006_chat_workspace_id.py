"""chat_conversations.workspace_id: one persisted thread per workspace chat (optional).

Revision ID: schema_006
Revises: schema_005
"""

from __future__ import annotations

from alembic import op

revision = "schema_006"
down_revision = "schema_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE chat_conversations
        ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES user_workspaces(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_conv_user_workspace
        ON chat_conversations (user_id, workspace_id)
        WHERE workspace_id IS NOT NULL;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_conv_workspace ON chat_conversations (workspace_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chat_conv_workspace;")
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_user_workspace;")
    op.execute("ALTER TABLE chat_conversations DROP COLUMN IF EXISTS workspace_id;")
