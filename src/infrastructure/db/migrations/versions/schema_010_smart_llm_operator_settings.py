"""Smart LLM routing settings in operator_settings (Web UI, not env).

Revision ID: schema_010
Revises: schema_009
"""

from __future__ import annotations

from alembic import op

revision = "schema_010"
down_revision = "schema_009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS llm_smart_routing_enabled BOOLEAN NOT NULL DEFAULT false,
          ADD COLUMN IF NOT EXISTS llm_router_ollama_model TEXT NOT NULL DEFAULT 'nemotron-3-nano:4b',
          ADD COLUMN IF NOT EXISTS llm_router_local_confidence_min DOUBLE PRECISION NOT NULL DEFAULT 0.7,
          ADD COLUMN IF NOT EXISTS llm_router_timeout_sec DOUBLE PRECISION NOT NULL DEFAULT 12,
          ADD COLUMN IF NOT EXISTS llm_route_long_prompt_chars INTEGER NOT NULL DEFAULT 8000,
          ADD COLUMN IF NOT EXISTS llm_route_short_local_max_chars INTEGER NOT NULL DEFAULT 220,
          ADD COLUMN IF NOT EXISTS llm_route_many_code_fences INTEGER NOT NULL DEFAULT 3,
          ADD COLUMN IF NOT EXISTS llm_route_many_messages INTEGER NOT NULL DEFAULT 14;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          DROP COLUMN IF EXISTS llm_smart_routing_enabled,
          DROP COLUMN IF EXISTS llm_router_ollama_model,
          DROP COLUMN IF EXISTS llm_router_local_confidence_min,
          DROP COLUMN IF EXISTS llm_router_timeout_sec,
          DROP COLUMN IF EXISTS llm_route_long_prompt_chars,
          DROP COLUMN IF EXISTS llm_route_short_local_max_chars,
          DROP COLUMN IF EXISTS llm_route_many_code_fences,
          DROP COLUMN IF EXISTS llm_route_many_messages;
        """
    )
