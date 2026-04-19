"""Generalize telegram_agent_sessions → bridge_agent_sessions (Telegram + Discord + future).

Revision ID: schema_013
Revises: schema_012
"""

from __future__ import annotations

from alembic import op

revision = "schema_013"
down_revision = "schema_012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.telegram_agent_sessions') IS NOT NULL
             AND to_regclass('public.bridge_agent_sessions') IS NULL THEN
            ALTER TABLE telegram_agent_sessions RENAME TO bridge_agent_sessions;
            ALTER INDEX IF EXISTS idx_telegram_agent_sessions_conv
              RENAME TO idx_bridge_agent_sessions_conv;
            ALTER TABLE bridge_agent_sessions RENAME COLUMN telegram_chat_id TO scope_chat_id;
            ALTER TABLE bridge_agent_sessions RENAME COLUMN telegram_thread_id TO scope_thread_id;
            ALTER TABLE bridge_agent_sessions
              ADD COLUMN provider TEXT NOT NULL DEFAULT 'telegram';
            ALTER TABLE bridge_agent_sessions DROP CONSTRAINT IF EXISTS telegram_agent_sessions_pkey;
            ALTER TABLE bridge_agent_sessions DROP CONSTRAINT IF EXISTS bridge_agent_sessions_pkey;
            ALTER TABLE bridge_agent_sessions
              ADD PRIMARY KEY (user_id, provider, scope_chat_id, scope_thread_id);
          END IF;
        END $$;
        """
    )
    # Greenfield (no schema_012): create ``bridge_agent_sessions`` directly.
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
    op.execute("DROP INDEX IF EXISTS idx_bridge_agent_sessions_conv;")
    op.execute("DROP TABLE IF EXISTS bridge_agent_sessions;")
