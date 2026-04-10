-- User persona (optional agent system injection; not for credentials).
CREATE TABLE IF NOT EXISTS user_agent_persona (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  instructions TEXT NOT NULL DEFAULT '',
  inject_into_agent BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_agent_persona_tenant ON user_agent_persona (tenant_id);

-- KB note read access: owner shares a note with another user in the same tenant.
CREATE TABLE IF NOT EXISTS user_kb_note_shares (
  id BIGSERIAL PRIMARY KEY,
  note_id BIGINT NOT NULL REFERENCES user_kb_notes(id) ON DELETE CASCADE,
  grantee_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  permission TEXT NOT NULL DEFAULT 'read',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT user_kb_note_shares_perm_check CHECK (permission IN ('read')),
  UNIQUE (note_id, grantee_user_id)
);

CREATE INDEX IF NOT EXISTS idx_kb_note_shares_grantee ON user_kb_note_shares (grantee_user_id);
CREATE INDEX IF NOT EXISTS idx_kb_note_shares_note ON user_kb_note_shares (note_id);
