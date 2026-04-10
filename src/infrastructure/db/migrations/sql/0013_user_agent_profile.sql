-- Structured user profile for agent context (no secrets). See docs/USER_DATA_AND_SECRETS.md
CREATE TABLE IF NOT EXISTS user_agent_profile (
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

  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_agent_profile_tenant ON user_agent_profile (tenant_id);
