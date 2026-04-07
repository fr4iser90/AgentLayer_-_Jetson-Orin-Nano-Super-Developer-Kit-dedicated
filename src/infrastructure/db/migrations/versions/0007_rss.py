"""0007 - rss articles

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0007_rss.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
