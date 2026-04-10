-- Operator override for AGENT_MODE (NULL = use process env AGENT_MODE).

ALTER TABLE operator_settings
    ADD COLUMN IF NOT EXISTS agent_mode TEXT;

COMMENT ON COLUMN operator_settings.agent_mode IS
    'sandbox | host; NULL = use AGENT_MODE from environment.';
