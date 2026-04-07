"""0004 - secret upload otps

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0004_secret_otps.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
