"""operator_settings: in-process Discord bot (token + bearer in DB, no extra container).

Revision ID: schema_003
Revises: schema_002
"""
from __future__ import annotations

from alembic import op

revision = "schema_003"
down_revision = "schema_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS discord_bot_enabled BOOLEAN NOT NULL DEFAULT false;"
    )
    op.execute("ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS discord_bot_token TEXT;")
    op.execute("ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS discord_bot_agent_bearer TEXT;")
    op.execute(
        "ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS discord_trigger_prefix TEXT NOT NULL DEFAULT '!agent ';"
    )
    op.execute("ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS discord_chat_model TEXT;")


def downgrade() -> None:
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS discord_chat_model;")
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS discord_trigger_prefix;")
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS discord_bot_agent_bearer;")
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS discord_bot_token;")
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS discord_bot_enabled;")
