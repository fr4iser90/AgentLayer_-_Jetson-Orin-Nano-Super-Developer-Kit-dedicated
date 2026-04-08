"""Squashed baseline schema (UUID users, operator_settings.optional_connection_key).

Revision ID: schema_001
Revises:
Create Date: 2026-04-08

Fresh databases only. Older installs used revisions 0001–0015; drop the DB volume
or create a new database before upgrading to this head.
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
