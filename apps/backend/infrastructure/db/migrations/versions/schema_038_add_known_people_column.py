"""
Add known_people jsonb column to user_agent_profile
"""

from __future__ import annotations

from alembic import op

revision = "schema_038"
down_revision = "schema_037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_agent_profile
        ADD COLUMN IF NOT EXISTS known_people jsonb NOT NULL DEFAULT '[]'::jsonb;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_agent_profile
        DROP COLUMN IF EXISTS known_people;
        """
    )