-- Operator-facing HTTP hints (optional overrides for multi-user headers).
CREATE TABLE IF NOT EXISTS operator_settings (
  id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  require_user_sub_header BOOLEAN NOT NULL DEFAULT false,
  user_sub_header_csv TEXT,
  tenant_id_header TEXT,
  discord_application_id TEXT,
  integration_notes TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO operator_settings (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;
