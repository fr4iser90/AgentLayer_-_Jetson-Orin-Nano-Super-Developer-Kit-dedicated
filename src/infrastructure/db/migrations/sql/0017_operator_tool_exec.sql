-- Operator override for where tool execution is allowed (NULL = use manifest).

ALTER TABLE operator_tool_policies
    ADD COLUMN IF NOT EXISTS execution_context TEXT;

COMMENT ON COLUMN operator_tool_policies.execution_context IS
    'Admin override: NULL = use package/per_tool manifest execution_context; '
    'otherwise host|container|remote|browser (normalized).';
