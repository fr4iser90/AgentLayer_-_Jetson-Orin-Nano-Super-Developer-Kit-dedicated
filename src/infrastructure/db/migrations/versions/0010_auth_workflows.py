"""0010 - auth system + workflows

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0010_auth_workflows.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
