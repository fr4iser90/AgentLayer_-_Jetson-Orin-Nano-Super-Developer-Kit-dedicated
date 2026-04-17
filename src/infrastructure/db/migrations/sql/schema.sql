-- Agent Layer — single baseline schema (one Alembic revision: schema_001).
-- Fresh PostgreSQL only: empty DB, then `alembic upgrade head`.
-- UUID user ids from the start; incremental migrations 0012–0021 were folded into this file.

CREATE TABLE tenants (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO tenants (id, name) VALUES (1, 'default')
ON CONFLICT (id) DO NOTHING;

SELECT setval(
  pg_get_serial_sequence('tenants', 'id'),
  GREATEST((SELECT COALESCE(MAX(id), 1) FROM tenants), 1)
);

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  external_sub TEXT NOT NULL,
  display_name TEXT,
  email TEXT UNIQUE,
  password_hash TEXT,
  role TEXT NOT NULL DEFAULT 'user',
  last_login_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  discord_user_id TEXT,
  UNIQUE (tenant_id, external_sub)
);

CREATE INDEX idx_users_tenant ON users (tenant_id);
CREATE INDEX idx_users_tenant_sub ON users (tenant_id, external_sub);
CREATE UNIQUE INDEX idx_users_tenant_discord_user ON users (tenant_id, discord_user_id)
  WHERE discord_user_id IS NOT NULL AND btrim(discord_user_id) <> '';

CREATE TABLE todos (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT todos_status_check CHECK (status IN ('open', 'done', 'cancelled'))
);

CREATE INDEX idx_todos_created_at ON todos (created_at DESC);
CREATE INDEX idx_todos_status ON todos (status);
CREATE INDEX idx_todos_tenant_user_created ON todos (tenant_id, user_id, created_at DESC);
CREATE INDEX idx_todos_user_status ON todos (user_id, status);

CREATE TABLE tool_invocations (
  id BIGSERIAL PRIMARY KEY,
  tool_name TEXT NOT NULL,
  args_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  result_excerpt TEXT,
  ok BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_tool_invocations_created_at ON tool_invocations (created_at DESC);
CREATE INDEX idx_tool_invocations_tool_name ON tool_invocations (tool_name);
CREATE INDEX idx_tool_inv_user_created ON tool_invocations (user_id, created_at DESC);
CREATE INDEX idx_tool_inv_tenant_user ON tool_invocations (tenant_id, user_id);

CREATE TABLE user_secrets (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  service_key TEXT NOT NULL,
  ciphertext BYTEA NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, service_key)
);

CREATE INDEX idx_user_secrets_user ON user_secrets (user_id);

CREATE TABLE secret_upload_otps (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  otp_hash TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_secret_otps_hash_unused ON secret_upload_otps (otp_hash)
  WHERE used_at IS NULL;

CREATE TABLE user_kb_notes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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

CREATE INDEX idx_user_kb_notes_tenant_user_created ON user_kb_notes (tenant_id, user_id, created_at DESC);
CREATE INDEX idx_user_kb_notes_tsv ON user_kb_notes USING GIN (search_tsv);

CREATE TABLE user_agent_persona (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  instructions TEXT NOT NULL DEFAULT '',
  inject_into_agent BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_agent_persona_tenant ON user_agent_persona (tenant_id);

CREATE TABLE user_kb_note_shares (
  id BIGSERIAL PRIMARY KEY,
  note_id BIGINT NOT NULL REFERENCES user_kb_notes(id) ON DELETE CASCADE,
  grantee_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  permission TEXT NOT NULL DEFAULT 'read',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT user_kb_note_shares_perm_check CHECK (permission IN ('read')),
  UNIQUE (note_id, grantee_user_id)
);

CREATE INDEX idx_kb_note_shares_grantee ON user_kb_note_shares (grantee_user_id);
CREATE INDEX idx_kb_note_shares_note ON user_kb_note_shares (note_id);

CREATE TABLE user_agent_profile (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

  display_name TEXT NOT NULL DEFAULT '',
  preferred_output_language TEXT NOT NULL DEFAULT '',
  locale TEXT NOT NULL DEFAULT '',
  timezone TEXT NOT NULL DEFAULT '',

  home_location TEXT NOT NULL DEFAULT '',
  work_location TEXT NOT NULL DEFAULT '',
  travel_mode TEXT NOT NULL DEFAULT '',
  travel_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,

  tone TEXT NOT NULL DEFAULT '',
  verbosity TEXT NOT NULL DEFAULT '',
  language_level TEXT NOT NULL DEFAULT '',

  interests JSONB NOT NULL DEFAULT '[]'::jsonb,
  hobbies JSONB NOT NULL DEFAULT '[]'::jsonb,

  job_title TEXT NOT NULL DEFAULT '',
  organization TEXT NOT NULL DEFAULT '',
  industry TEXT NOT NULL DEFAULT '',
  experience_level TEXT NOT NULL DEFAULT '',
  primary_tools JSONB NOT NULL DEFAULT '[]'::jsonb,

  proactive_mode BOOLEAN NOT NULL DEFAULT false,
  interaction_style TEXT NOT NULL DEFAULT '',

  inject_structured_profile BOOLEAN NOT NULL DEFAULT true,
  inject_dynamic_traits BOOLEAN NOT NULL DEFAULT false,
  dynamic_traits JSONB NOT NULL DEFAULT '{}'::jsonb,

  profile_version BIGINT NOT NULL DEFAULT 1,
  profile_hash TEXT NOT NULL DEFAULT '',
  injection_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
  usage_patterns JSONB NOT NULL DEFAULT '{}'::jsonb,

  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_agent_profile_tenant ON user_agent_profile (tenant_id);

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_documents (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  domain TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  source_uri TEXT,
  content_sha256 TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rag_documents_scope ON rag_documents (tenant_id, user_id, domain);

CREATE TABLE rag_chunks (
  id BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  embedding vector(768) NOT NULL,
  UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_rag_chunks_document ON rag_chunks (document_id);
CREATE INDEX idx_rag_chunks_embedding ON rag_chunks USING hnsw (embedding vector_cosine_ops);

-- --- User memory: structured facts + semantic notes ---

CREATE TABLE user_memory_facts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id UUID NULL REFERENCES user_workspaces(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  value_json JSONB NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0,
  source TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NULL,
  deleted_at TIMESTAMPTZ NULL
);

CREATE UNIQUE INDEX ux_user_memory_facts_global_key
  ON user_memory_facts (tenant_id, user_id, key)
  WHERE workspace_id IS NULL AND deleted_at IS NULL;

CREATE UNIQUE INDEX ux_user_memory_facts_workspace_key
  ON user_memory_facts (tenant_id, user_id, workspace_id, key)
  WHERE workspace_id IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX idx_user_memory_facts_scope_updated
  ON user_memory_facts (tenant_id, user_id, workspace_id, updated_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_user_memory_facts_scope_expires
  ON user_memory_facts (tenant_id, user_id, workspace_id, expires_at)
  WHERE deleted_at IS NULL;

CREATE TABLE user_memory_notes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id UUID NULL REFERENCES user_workspaces(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL,
  embedding vector(768) NOT NULL
);

CREATE INDEX idx_user_memory_notes_scope_updated
  ON user_memory_notes (tenant_id, user_id, workspace_id, updated_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX idx_user_memory_notes_embedding
  ON user_memory_notes USING hnsw (embedding vector_cosine_ops);

CREATE TABLE rss_articles (
  id BIGSERIAL PRIMARY KEY,
  article_id TEXT NOT NULL UNIQUE,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_rss_articles_fetched ON rss_articles (fetched_at DESC);

CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  last_used_at TIMESTAMPTZ
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);

CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_hash TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);

CREATE TABLE workflows (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  definition JSONB NOT NULL DEFAULT '{}'::jsonb,
  visibility TEXT NOT NULL DEFAULT 'private',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workflows_owner ON workflows(owner_user_id);

CREATE TABLE workflow_permissions (
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  can_execute BOOLEAN NOT NULL DEFAULT false,
  can_edit BOOLEAN NOT NULL DEFAULT false,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (workflow_id, user_id)
);

CREATE TABLE admin_claim_otp (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  otp_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  claimed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_admin_claim_otp_pending ON admin_claim_otp (created_at DESC)
  WHERE used_at IS NULL;

CREATE TABLE operator_settings (
  id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  discord_application_id TEXT,
  integration_notes TEXT,
  optional_connection_key TEXT,
  agent_mode TEXT,
  discord_bot_enabled BOOLEAN NOT NULL DEFAULT false,
  discord_bot_token TEXT,
  discord_bot_agent_bearer TEXT,
  discord_trigger_prefix TEXT NOT NULL DEFAULT '!agent ',
  discord_chat_model TEXT,
  workspace_upload_max_file_mb INTEGER,
  workspace_upload_allowed_mime TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO operator_settings (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE operator_tool_policies (
  package_id TEXT NOT NULL,
  tool_name TEXT NOT NULL DEFAULT '*',
  enabled BOOLEAN NOT NULL DEFAULT true,
  min_role TEXT NOT NULL DEFAULT 'user',
  allowed_tenant_ids INTEGER[],
  execution_context TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (package_id, tool_name),
  CONSTRAINT operator_tool_policies_min_role_check CHECK (min_role IN ('user', 'admin'))
);

CREATE INDEX idx_operator_tool_policies_package ON operator_tool_policies (package_id);

COMMENT ON COLUMN operator_tool_policies.min_role IS
  'Minimum users.role required to list/invoke tools in this package (user = all authenticated users).';
COMMENT ON COLUMN operator_tool_policies.allowed_tenant_ids IS
  'NULL = any tenant; non-empty = only these tenant ids may use the package.';

COMMENT ON COLUMN operator_settings.agent_mode IS
  'sandbox | host; NULL = use AGENT_MODE from environment.';
COMMENT ON COLUMN operator_settings.workspace_upload_max_file_mb IS
  'Max upload size per file (MB); NULL = use AGENT_WORKSPACE_UPLOAD_MAX_MB.';
COMMENT ON COLUMN operator_settings.workspace_upload_allowed_mime IS
  'Comma-separated MIME allowlist; NULL = use AGENT_WORKSPACE_UPLOAD_ALLOWED_MIME.';

CREATE TABLE workspace_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL,
  storage_relpath TEXT NOT NULL UNIQUE,
  content_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  original_name TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workspace_files_owner ON workspace_files (owner_user_id, created_at DESC);
CREATE INDEX idx_workspace_files_workspace ON workspace_files (workspace_id);

CREATE TABLE workspace_members (
  workspace_id UUID NOT NULL,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('viewer', 'editor', 'co_owner')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX idx_workspace_members_user ON workspace_members (user_id);

-- Server-side chat threads (first-party UI sync; per user, per tenant).

CREATE TABLE chat_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES user_workspaces(id) ON DELETE SET NULL,
  title TEXT NOT NULL DEFAULT '',
  mode TEXT NOT NULL DEFAULT 'chat' CHECK (mode IN ('chat', 'agent')),
  model TEXT NOT NULL DEFAULT '',
  agent_log JSONB NOT NULL DEFAULT '[]'::jsonb,
  shared BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_conv_user_updated ON chat_conversations (user_id, updated_at DESC);
CREATE INDEX idx_chat_conv_tenant ON chat_conversations (tenant_id);
CREATE INDEX idx_chat_conv_workspace ON chat_conversations (workspace_id);
CREATE UNIQUE INDEX uq_chat_conv_user_workspace_personal
  ON chat_conversations (user_id, workspace_id)
  WHERE workspace_id IS NOT NULL AND shared = false;
CREATE UNIQUE INDEX uq_chat_conv_workspace_shared
  ON chat_conversations (workspace_id)
  WHERE workspace_id IS NOT NULL AND shared = true;

CREATE TABLE chat_messages (
  id BIGSERIAL PRIMARY KEY,
  conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  position INT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (conversation_id, position)
);

CREATE INDEX idx_chat_msg_conv ON chat_messages (conversation_id, position);
