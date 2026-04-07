"""0005 - user kb notes

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0005_kb_notes.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
