"""0001 - initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0001_init.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
