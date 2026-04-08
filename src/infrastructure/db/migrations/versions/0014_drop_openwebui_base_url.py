"""0014 - Remove openwebui_base_url from operator_settings

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-08
"""
from alembic import op
import os

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "0014_drop_openwebui_base_url.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS openwebui_base_url TEXT")
