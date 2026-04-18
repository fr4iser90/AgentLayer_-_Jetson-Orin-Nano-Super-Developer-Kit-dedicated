"""Telegram bot settings (operator_settings) and users.telegram_user_id — parity with Discord.

Revision ID: schema_011
Revises: schema_010
"""

from __future__ import annotations

from alembic import op

revision = "schema_011"
down_revision = "schema_010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_user_id TEXT;")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tenant_telegram_user
        ON users (tenant_id, telegram_user_id)
        WHERE telegram_user_id IS NOT NULL AND btrim(telegram_user_id) <> '';
        """
    )
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS telegram_application_id TEXT,
          ADD COLUMN IF NOT EXISTS telegram_bot_enabled BOOLEAN NOT NULL DEFAULT false,
          ADD COLUMN IF NOT EXISTS telegram_bot_token TEXT,
          ADD COLUMN IF NOT EXISTS telegram_bot_agent_bearer TEXT,
          ADD COLUMN IF NOT EXISTS telegram_trigger_prefix TEXT NOT NULL DEFAULT '!agent ',
          ADD COLUMN IF NOT EXISTS telegram_chat_model TEXT;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_tenant_telegram_user;")
    op.execute(
        """
        ALTER TABLE operator_settings
          DROP COLUMN IF EXISTS telegram_chat_model,
          DROP COLUMN IF EXISTS telegram_trigger_prefix,
          DROP COLUMN IF EXISTS telegram_bot_agent_bearer,
          DROP COLUMN IF EXISTS telegram_bot_token,
          DROP COLUMN IF EXISTS telegram_bot_enabled,
          DROP COLUMN IF EXISTS telegram_application_id;
        """
    )
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS telegram_user_id;")
