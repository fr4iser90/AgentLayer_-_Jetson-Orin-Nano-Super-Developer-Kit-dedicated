CREATE TABLE IF NOT EXISTS user_kb_notes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  search_tsv tsvector GENERATED ALWAYS AS (
    to_tsvector(
      'simple',
      coalesce(title, '') || ' ' || coalesce(body, '')
    )
  ) STORED
);

CREATE INDEX IF NOT EXISTS idx_user_kb_notes_tenant_user_created
  ON user_kb_notes (tenant_id, user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_kb_notes_tsv
  ON user_kb_notes USING GIN (search_tsv);
