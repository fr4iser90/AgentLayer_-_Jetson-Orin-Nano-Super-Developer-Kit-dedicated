"""0002 - multitenant + users

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0002_multitenant.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
