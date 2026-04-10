"""profile_version, profile_hash, injection_preferences, usage_patterns.

Revision ID must fit alembic_version.version_num (VARCHAR(32)).
Revises: 0013_user_agent_profile
"""
from __future__ import annotations

import os

from alembic import op

revision = "0014_profile_inj_prefs"
down_revision = "0013_user_agent_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sql_file = os.path.join(
        os.path.dirname(__file__), "..", "sql", "0014_profile_inj_prefs.sql"
    )
    with open(sql_file, encoding="utf-8") as f:
        op.execute(f.read())


def downgrade() -> None:
    op.execute("ALTER TABLE user_agent_profile DROP COLUMN IF EXISTS usage_patterns")
    op.execute("ALTER TABLE user_agent_profile DROP COLUMN IF EXISTS injection_preferences")
    op.execute("ALTER TABLE user_agent_profile DROP COLUMN IF EXISTS profile_hash")
    op.execute("ALTER TABLE user_agent_profile DROP COLUMN IF EXISTS profile_version")
