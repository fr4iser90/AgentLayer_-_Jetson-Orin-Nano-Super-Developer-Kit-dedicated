"""0011 - admin claim OTP table

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-08
"""
from alembic import op
import os

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "0011_admin_claim_otp.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_claim_otp")
