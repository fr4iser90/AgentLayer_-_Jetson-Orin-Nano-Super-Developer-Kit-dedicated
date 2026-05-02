"""chat_conversations.dashboard_id: one persisted thread per dashboard chat (optional).

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
        ADD COLUMN IF NOT EXISTS dashboard_id UUID REFERENCES user_dashboards(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_conv_user_dashboard
        ON chat_conversations (user_id, dashboard_id)
        WHERE dashboard_id IS NOT NULL;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_conv_dashboard ON chat_conversations (dashboard_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chat_conv_dashboard;")
    op.execute("DROP INDEX IF EXISTS uq_chat_conv_user_dashboard;")
    op.execute("ALTER TABLE chat_conversations DROP COLUMN IF EXISTS dashboard_id;")
