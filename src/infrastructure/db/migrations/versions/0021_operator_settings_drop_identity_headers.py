"""Drop operator_settings identity-header columns (unused; identity is Bearer-only).

Revises: 0020_operator_tool_policy_access
Revision id must be <= 32 chars (alembic_version.version_num).

Create Date: 2026-04-08
"""

import os

from alembic import op

# alembic_version.version_num is VARCHAR(32); keep revision id <= 32 chars.
revision = "0021_opset_hdrdrop"
down_revision = "0020_operator_tool_policy_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_path = os.path.join(
        os.path.dirname(__file__), "..", "sql", "0021_operator_settings_drop_identity_headers.sql"
    )
    with open(sql_path, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute(
        "ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS require_user_sub_header BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS user_sub_header_csv TEXT")
    op.execute("ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS tenant_id_header TEXT")
