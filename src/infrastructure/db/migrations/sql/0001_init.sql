CREATE TABLE IF NOT EXISTS todos (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT todos_status_check CHECK (status IN ('open', 'done', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_todos_created_at ON todos (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_todos_status ON todos (status);

CREATE TABLE IF NOT EXISTS tool_invocations (
  id BIGSERIAL PRIMARY KEY,
  tool_name TEXT NOT NULL,
  args_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  result_excerpt TEXT,
  ok BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tool_invocations_created_at
  ON tool_invocations (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_tool_name
  ON tool_invocations (tool_name);
