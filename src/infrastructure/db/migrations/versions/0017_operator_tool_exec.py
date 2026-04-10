"""Add execution_context to operator_tool_policies.

Revision ID must fit alembic_version.version_num (VARCHAR(32)).
Revises: 0016_operator_tool_policies
"""
from __future__ import annotations

import os

from alembic import op

revision = "0017_operator_tool_exec"
down_revision = "0016_operator_tool_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(
        os.path.dirname(__file__), "..", "sql", "0017_operator_tool_exec.sql"
    )
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("ALTER TABLE operator_tool_policies DROP COLUMN IF EXISTS execution_context")
