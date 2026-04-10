-- Operator overrides for tool packages / single tools (manifest defaults in code; DB stores overrides).

CREATE TABLE operator_tool_policies (
    package_id TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '*',
    enabled BOOLEAN NOT NULL DEFAULT true,
    default_on BOOLEAN,
    user_configurable BOOLEAN,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (package_id, tool_name)
);

CREATE INDEX idx_operator_tool_policies_package ON operator_tool_policies (package_id);

COMMENT ON TABLE operator_tool_policies IS
    'Admin overrides: enabled gates exposure in GET /v1/tools; default_on/user_configurable override manifest when set. tool_name * = whole package.';
