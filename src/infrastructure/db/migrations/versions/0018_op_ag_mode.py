"""Add agent_mode to operator_settings (AGENT_MODE Web override).

Revises: 0017_operator_tool_exec
"""
from __future__ import annotations

import os

from alembic import op

revision = "0018_op_ag_mode"
down_revision = "0017_operator_tool_exec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(
        os.path.dirname(__file__), "..", "sql", "0018_operator_settings_agent_mode.sql"
    )
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS agent_mode")
