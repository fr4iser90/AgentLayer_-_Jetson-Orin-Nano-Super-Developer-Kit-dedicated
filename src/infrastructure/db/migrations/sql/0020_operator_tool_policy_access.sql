-- Replace default_on / user_configurable with role + tenant access gates.

ALTER TABLE operator_tool_policies
    ADD COLUMN IF NOT EXISTS min_role TEXT NOT NULL DEFAULT 'user',
    ADD COLUMN IF NOT EXISTS allowed_tenant_ids INTEGER[];

UPDATE operator_tool_policies SET min_role = 'user' WHERE min_role IS NULL OR trim(min_role) = '';

ALTER TABLE operator_tool_policies DROP CONSTRAINT IF EXISTS operator_tool_policies_min_role_check;
ALTER TABLE operator_tool_policies
    ADD CONSTRAINT operator_tool_policies_min_role_check
    CHECK (min_role IN ('user', 'admin'));

-- Former "admin-only lock" (user_configurable = false) → require admin role.
UPDATE operator_tool_policies SET min_role = 'admin'
WHERE user_configurable IS NOT NULL AND user_configurable = false;

ALTER TABLE operator_tool_policies DROP COLUMN IF EXISTS default_on;
ALTER TABLE operator_tool_policies DROP COLUMN IF EXISTS user_configurable;

COMMENT ON COLUMN operator_tool_policies.min_role IS
    'Minimum users.role required to list/invoke tools in this package (user = all authenticated users).';
COMMENT ON COLUMN operator_tool_policies.allowed_tenant_ids IS
    'NULL = any tenant; non-empty = only these tenant ids may use the package.';
