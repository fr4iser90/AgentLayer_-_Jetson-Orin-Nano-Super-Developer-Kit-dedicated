"""0009 - prepare UUID migration (guarded)

Revision ID: 0009
Revises: 0007
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0009'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0009_uuid_prep.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
