CREATE TABLE IF NOT EXISTS tenants (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  external_sub TEXT NOT NULL,
  display_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, external_sub)
);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users (tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant_sub ON users (tenant_id, external_sub);

INSERT INTO tenants (id, name) VALUES (1, 'default')
ON CONFLICT (id) DO NOTHING;

SELECT setval(
  pg_get_serial_sequence('tenants', 'id'),
  GREATEST((SELECT COALESCE(MAX(id), 1) FROM tenants), 1)
);

INSERT INTO users (id, tenant_id, external_sub, display_name)
VALUES (1, 1, 'default', 'Default user')
ON CONFLICT (tenant_id, external_sub) DO NOTHING;

SELECT setval(
  pg_get_serial_sequence('users', 'id'),
  GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1)
);

ALTER TABLE todos ADD COLUMN IF NOT EXISTS tenant_id BIGINT;
ALTER TABLE todos ADD COLUMN IF NOT EXISTS user_id BIGINT;
UPDATE todos SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE todos SET user_id = 1 WHERE user_id IS NULL;
ALTER TABLE todos ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE todos ALTER COLUMN user_id SET NOT NULL;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'todos_tenant_id_fkey'
  ) THEN
    ALTER TABLE todos ADD CONSTRAINT todos_tenant_id_fkey
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'todos_user_id_fkey'
  ) THEN
    ALTER TABLE todos ADD CONSTRAINT todos_user_id_fkey
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_todos_tenant_user_created
  ON todos (tenant_id, user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_user_status ON todos (user_id, status);

ALTER TABLE tool_invocations ADD COLUMN IF NOT EXISTS tenant_id BIGINT;
ALTER TABLE tool_invocations ADD COLUMN IF NOT EXISTS user_id BIGINT;
UPDATE tool_invocations SET tenant_id = 1 WHERE tenant_id IS NULL;
UPDATE tool_invocations SET user_id = 1 WHERE user_id IS NULL;
ALTER TABLE tool_invocations ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE tool_invocations ALTER COLUMN user_id SET NOT NULL;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tool_invocations_tenant_id_fkey'
  ) THEN
    ALTER TABLE tool_invocations ADD CONSTRAINT tool_invocations_tenant_id_fkey
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'tool_invocations_user_id_fkey'
  ) THEN
    ALTER TABLE tool_invocations ADD CONSTRAINT tool_invocations_user_id_fkey
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tool_inv_user_created
  ON tool_invocations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_inv_tenant_user
  ON tool_invocations (tenant_id, user_id);
