-- Removed: identity was never to be driven by configurable HTTP headers (use Bearer + users.tenant_id).

ALTER TABLE operator_settings DROP COLUMN IF EXISTS require_user_sub_header;
ALTER TABLE operator_settings DROP COLUMN IF EXISTS user_sub_header_csv;
ALTER TABLE operator_settings DROP COLUMN IF EXISTS tenant_id_header;
