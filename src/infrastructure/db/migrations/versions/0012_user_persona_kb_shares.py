"""user_agent_persona + user_kb_note_shares (persona injection + KB sharing).

Revision ID: 0012_user_persona_kb_shares
Revises: schema_001
"""
from __future__ import annotations

import os

from alembic import op

revision = "0012_user_persona_kb_shares"
down_revision = "schema_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "0012_user_persona_kb_shares.sql")
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_kb_note_shares")
    op.execute("DROP TABLE IF EXISTS user_agent_persona")
