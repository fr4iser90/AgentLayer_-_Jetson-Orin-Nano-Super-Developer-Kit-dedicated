-- Open WebUI API key hint (operator copies into WebUI).
ALTER TABLE operator_settings ADD COLUMN IF NOT EXISTS openwebui_bearer TEXT;
