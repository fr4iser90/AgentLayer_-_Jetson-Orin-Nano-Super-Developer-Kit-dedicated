"""Tool policy: min_role + allowed_tenant_ids; drop default_on / user_configurable.

Revises: 0018_op_ag_mode
Create Date: 2026-04-08
"""

import os

from alembic import op

revision = "0020_operator_tool_policy_access"
down_revision = "0018_op_ag_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "0020_operator_tool_policy_access.sql")
    with open(sql_path, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("ALTER TABLE operator_tool_policies DROP CONSTRAINT IF EXISTS operator_tool_policies_min_role_check")
    op.execute("ALTER TABLE operator_tool_policies DROP COLUMN IF EXISTS allowed_tenant_ids")
    op.execute("ALTER TABLE operator_tool_policies DROP COLUMN IF EXISTS min_role")
    op.execute(
        "ALTER TABLE operator_tool_policies ADD COLUMN IF NOT EXISTS default_on BOOLEAN"
    )
    op.execute(
        "ALTER TABLE operator_tool_policies ADD COLUMN IF NOT EXISTS user_configurable BOOLEAN"
    )
