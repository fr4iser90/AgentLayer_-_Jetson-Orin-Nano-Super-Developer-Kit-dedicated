"""0006 - rag documents + chunks

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0006_rag.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
