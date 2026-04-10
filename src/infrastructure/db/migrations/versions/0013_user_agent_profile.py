"""Structured user_agent_profile (preferences, travel, tools, agent behavior).

Revision ID: 0013_user_agent_profile
Revises: 0012_user_persona_kb_shares
"""
from __future__ import annotations

import os

from alembic import op

revision = "0013_user_agent_profile"
down_revision = "0012_user_persona_kb_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "0013_user_agent_profile.sql")
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_agent_profile")
