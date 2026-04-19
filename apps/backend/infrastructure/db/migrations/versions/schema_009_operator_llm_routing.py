"""Operator LLM routing: primary backend Ollama vs external OpenAI-compatible API.

Revision ID: schema_009
Revises: schema_008
"""

from __future__ import annotations

from alembic import op

revision = "schema_009"
down_revision = "schema_008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS llm_primary_backend TEXT NOT NULL DEFAULT 'ollama',
          ADD COLUMN IF NOT EXISTS llm_external_base_url TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_api_key TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_default TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_vlm TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_agent TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_coding TEXT;
        """
    )
    op.execute(
        """
        UPDATE operator_settings SET llm_primary_backend = 'ollama'
        WHERE id = 1 AND (llm_primary_backend IS NULL OR llm_primary_backend = '');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          DROP COLUMN IF EXISTS llm_primary_backend,
          DROP COLUMN IF EXISTS llm_external_base_url,
          DROP COLUMN IF EXISTS llm_external_api_key,
          DROP COLUMN IF EXISTS llm_external_model_default,
          DROP COLUMN IF EXISTS llm_external_model_vlm,
          DROP COLUMN IF EXISTS llm_external_model_agent,
          DROP COLUMN IF EXISTS llm_external_model_coding;
        """
    )
