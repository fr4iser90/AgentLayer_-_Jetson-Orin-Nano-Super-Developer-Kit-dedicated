"""Operator settings: graph memory knobs (DB-backed, no env).

Revision ID: schema_020
Revises: schema_019
"""

from __future__ import annotations

from alembic import op

revision = "schema_020"
down_revision = "schema_019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS memory_graph_enabled BOOLEAN NOT NULL DEFAULT true,
          ADD COLUMN IF NOT EXISTS memory_graph_max_hops INTEGER NOT NULL DEFAULT 2,
          ADD COLUMN IF NOT EXISTS memory_graph_min_score DOUBLE PRECISION NOT NULL DEFAULT 0.03,
          ADD COLUMN IF NOT EXISTS memory_graph_max_bullets INTEGER NOT NULL DEFAULT 14,
          ADD COLUMN IF NOT EXISTS memory_graph_max_prompt_chars INTEGER NOT NULL DEFAULT 3500,
          ADD COLUMN IF NOT EXISTS memory_graph_log_activations BOOLEAN NOT NULL DEFAULT false;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          DROP COLUMN IF EXISTS memory_graph_log_activations,
          DROP COLUMN IF EXISTS memory_graph_max_prompt_chars,
          DROP COLUMN IF EXISTS memory_graph_max_bullets,
          DROP COLUMN IF EXISTS memory_graph_min_score,
          DROP COLUMN IF EXISTS memory_graph_max_hops,
          DROP COLUMN IF EXISTS memory_graph_enabled;
        """
    )
