"""Single baseline migration — applies ``sql/schema.sql`` (full current schema).

Revision ID: schema_001
Revises: (none)
Head: this revision only.

Use on empty databases: ``alembic upgrade head``. Older incremental revisions were removed;
existing deployments should dump data, recreate DB, restore data if needed, or keep a backup branch.
"""
from __future__ import annotations

import os

from alembic import op

revision = "schema_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "schema.sql")
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    pass
