"""chat_conversations + chat_messages for server-synced UI threads.

Revision ID must fit alembic_version.version_num (VARCHAR(32)).
Revises: 0014_profile_inj_prefs
"""
from __future__ import annotations

import os

from alembic import op

revision = "0015_chat_conversations"
down_revision = "0014_profile_inj_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(
        os.path.dirname(__file__), "..", "sql", "0015_chat_conversations.sql"
    )
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chat_messages")
    op.execute("DROP TABLE IF EXISTS chat_conversations")
