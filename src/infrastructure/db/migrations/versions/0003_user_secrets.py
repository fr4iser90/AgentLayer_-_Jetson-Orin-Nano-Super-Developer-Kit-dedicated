"""0003 - user secrets

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-07
"""
from alembic import op
import os

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'sql', '0003_user_secrets.sql')
    with open(sql_file, 'r') as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
