"""Add users.discord_user_id for Web UI → Discord bot identity mapping.

Revision ID: schema_002
Revises: schema_001
"""
from __future__ import annotations

from alembic import op

revision = "schema_002"
down_revision = "schema_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS discord_user_id TEXT;")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tenant_discord_user
        ON users (tenant_id, discord_user_id)
        WHERE discord_user_id IS NOT NULL AND btrim(discord_user_id) <> '';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_users_tenant_discord_user;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS discord_user_id;")
