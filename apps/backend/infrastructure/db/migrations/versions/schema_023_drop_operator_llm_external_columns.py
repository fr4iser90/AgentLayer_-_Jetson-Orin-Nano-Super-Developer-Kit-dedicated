"""Remove legacy llm_external_* columns from operator_settings (external LLM is operator_external_llm_endpoints only).

Revision ID: schema_023
Revises: schema_022
"""

from __future__ import annotations

from alembic import op

revision = "schema_023"
down_revision = "schema_022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          DROP COLUMN IF EXISTS llm_external_base_url,
          DROP COLUMN IF EXISTS llm_external_api_key,
          DROP COLUMN IF EXISTS llm_external_model_default,
          DROP COLUMN IF EXISTS llm_external_model_vlm,
          DROP COLUMN IF EXISTS llm_external_model_agent,
          DROP COLUMN IF EXISTS llm_external_model_coding;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE operator_settings
          ADD COLUMN IF NOT EXISTS llm_external_base_url TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_api_key TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_default TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_vlm TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_agent TEXT,
          ADD COLUMN IF NOT EXISTS llm_external_model_coding TEXT;
        """
    )
