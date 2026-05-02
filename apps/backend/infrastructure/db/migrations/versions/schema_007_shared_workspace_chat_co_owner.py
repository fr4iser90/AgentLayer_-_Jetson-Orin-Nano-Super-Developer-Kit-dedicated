"""Shared dashboard chat (one thread per dashboard) + co_owner member role.

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
        ALTER TABLE dashboard_members DROP CONSTRAINT IF EXISTS dashboard_members_role_check;
        """
    )
    op.execute(
        """
        ALTER TABLE dashboard_members ADD CONSTRAINT dashboard_members_role_check
        CHECK (role IN ('viewer', 'editor', 'co_owner'));
        """
    )
    op.execute(
        """
        ALTER TABLE chat_conversations
        ADD COLUMN IF NOT EXISTS shared BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_user_dashboard;")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_conv_user_dashboard_personal
        ON chat_conversations (user_id, dashboard_id)
        WHERE dashboard_id IS NOT NULL AND shared = false;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_conv_dashboard_shared
        ON chat_conversations (dashboard_id)
        WHERE dashboard_id IS NOT NULL AND shared = true;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_dashboard_shared;")
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_user_dashboard_personal;")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_chat_conv_user_dashboard
        ON chat_conversations (user_id, dashboard_id)
        WHERE dashboard_id IS NOT NULL;
        """
    )
    op.execute("ALTER TABLE chat_conversations DROP COLUMN IF EXISTS shared;")
    op.execute(
        """
        ALTER TABLE dashboard_members DROP CONSTRAINT IF EXISTS dashboard_members_role_check;
        """
    )
    op.execute(
        """
        ALTER TABLE dashboard_members ADD CONSTRAINT dashboard_members_role_check
        CHECK (role IN ('viewer', 'editor'));
        """
    )