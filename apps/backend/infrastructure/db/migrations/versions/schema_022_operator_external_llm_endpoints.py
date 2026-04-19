"""Multiple external OpenAI-compatible LLM endpoints (URL + key + profile models, failover order).

Revision ID: schema_022
Revises: schema_021
"""

from __future__ import annotations

from alembic import op

revision = "schema_022"
down_revision = "schema_021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_external_llm_endpoints (
          id BIGSERIAL PRIMARY KEY,
          sort_order INTEGER NOT NULL DEFAULT 0,
          enabled BOOLEAN NOT NULL DEFAULT true,
          label TEXT NOT NULL DEFAULT '',
          base_url TEXT NOT NULL,
          api_key TEXT NOT NULL,
          model_default TEXT,
          model_vlm TEXT,
          model_agent TEXT,
          model_coding TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operator_external_llm_endpoints_sort
          ON operator_external_llm_endpoints (sort_order ASC, id ASC);
        """
    )
    # Seed one row from legacy operator_settings when URL + key exist.
    op.execute(
        """
        INSERT INTO operator_external_llm_endpoints (
          sort_order, enabled, label, base_url, api_key,
          model_default, model_vlm, model_agent, model_coding
        )
        SELECT
          0, true, 'default',
          NULLIF(btrim(COALESCE(llm_external_base_url, '')), ''),
          COALESCE(btrim(llm_external_api_key), ''),
          NULLIF(btrim(COALESCE(llm_external_model_default, '')), ''),
          NULLIF(btrim(COALESCE(llm_external_model_vlm, '')), ''),
          NULLIF(btrim(COALESCE(llm_external_model_agent, '')), ''),
          NULLIF(btrim(COALESCE(llm_external_model_coding, '')), '')
        FROM operator_settings WHERE id = 1
          AND NULLIF(btrim(COALESCE(llm_external_base_url, '')), '') IS NOT NULL
          AND btrim(COALESCE(llm_external_api_key, '')) <> '';
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS operator_external_llm_endpoints;")
