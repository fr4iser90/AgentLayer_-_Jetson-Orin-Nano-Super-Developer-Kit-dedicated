"""0013 - Open WebUI base URL / bearer hints on operator_settings

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-08
"""
from alembic import op
import os

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "0013_openwebui_interface_hints.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS openwebui_bearer")
    op.execute("ALTER TABLE operator_settings DROP COLUMN IF EXISTS openwebui_base_url")
