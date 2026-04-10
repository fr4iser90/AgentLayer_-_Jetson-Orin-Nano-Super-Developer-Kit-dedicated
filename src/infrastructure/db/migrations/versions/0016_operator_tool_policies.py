"""operator_tool_policies for admin tool toggles.

Revision ID must fit alembic_version.version_num (VARCHAR(32)).
Revises: 0015_chat_conversations
"""
from __future__ import annotations

import os

from alembic import op

revision = "0016_operator_tool_policies"
down_revision = "0015_chat_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(
        os.path.dirname(__file__), "..", "sql", "0016_operator_tool_policies.sql"
    )
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS operator_tool_policies")
