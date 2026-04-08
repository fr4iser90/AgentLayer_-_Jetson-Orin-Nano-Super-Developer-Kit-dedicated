"""0012 - operator console settings (headers / integration hints)

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-08
"""
from alembic import op
import os

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "0012_operator_settings.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS operator_settings")
