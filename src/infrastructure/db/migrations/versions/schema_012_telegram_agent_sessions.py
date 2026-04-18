"""Bridge chat sessions (Telegram, Discord, …) → ``chat_conversations`` for rolling context.

Revision ID: schema_012
Revises: schema_011
"""

from __future__ import annotations

from alembic import op

revision = "schema_012"
down_revision = "schema_011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bridge_agent_sessions (
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          provider TEXT NOT NULL,
          scope_chat_id BIGINT NOT NULL,
          scope_thread_id BIGINT NOT NULL DEFAULT 0,
          conversation_id UUID NOT NULL UNIQUE
            REFERENCES chat_conversations(id) ON DELETE CASCADE,
          PRIMARY KEY (user_id, provider, scope_chat_id, scope_thread_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_bridge_agent_sessions_conv "
        "ON bridge_agent_sessions(conversation_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bridge_agent_sessions;")
