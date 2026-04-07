-- Convert users.id from BIGINT to UUID
-- Split/guarded version for safety

-- 1. Remove foreign keys (only if the tables exist)
ALTER TABLE IF EXISTS refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_user_id_fkey;
ALTER TABLE IF EXISTS api_keys DROP CONSTRAINT IF EXISTS api_keys_user_id_fkey;
ALTER TABLE IF EXISTS workflows DROP CONSTRAINT IF EXISTS workflows_owner_user_id_fkey;
ALTER TABLE IF EXISTS workflow_permissions DROP CONSTRAINT IF EXISTS workflow_permissions_user_id_fkey;
ALTER TABLE IF EXISTS todos DROP CONSTRAINT IF EXISTS todos_user_id_fkey;
ALTER TABLE IF EXISTS tool_invocations DROP CONSTRAINT IF EXISTS tool_invocations_user_id_fkey;
ALTER TABLE IF EXISTS user_secrets DROP CONSTRAINT IF EXISTS user_secrets_user_id_fkey;
ALTER TABLE IF EXISTS secret_upload_otps DROP CONSTRAINT IF EXISTS secret_upload_otps_user_id_fkey;
ALTER TABLE IF EXISTS user_kb_notes DROP CONSTRAINT IF EXISTS user_kb_notes_user_id_fkey;
ALTER TABLE IF EXISTS rag_documents DROP CONSTRAINT IF EXISTS rag_documents_user_id_fkey;

-- 2. Prepare users table
ALTER TABLE users ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE IF EXISTS users_id_seq CASCADE;

-- 3. Add temporary uuid column
ALTER TABLE users ADD COLUMN IF NOT EXISTS uuid UUID UNIQUE DEFAULT gen_random_uuid();
UPDATE users SET uuid = ('00000000-0000-4000-8000-' || lpad(to_hex(id), 12, '0'))::uuid WHERE id < 1000000;

-- 4. FIRST convert foreign key columns to TEXT (only if the table exists)
ALTER TABLE IF EXISTS refresh_tokens ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS api_keys ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS workflows ALTER COLUMN owner_user_id TYPE TEXT;
ALTER TABLE IF EXISTS workflow_permissions ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS todos ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS tool_invocations ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS user_secrets ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS secret_upload_otps ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS user_kb_notes ALTER COLUMN user_id TYPE TEXT;
ALTER TABLE IF EXISTS rag_documents ALTER COLUMN user_id TYPE TEXT;

-- 5. Update ALL foreign keys NOW (guard each UPDATE so missing tables are skipped)
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'refresh_tokens') THEN
    UPDATE refresh_tokens SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_keys') THEN
    UPDATE api_keys SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'workflows') THEN
    UPDATE workflows SET owner_user_id = (SELECT uuid::text FROM users WHERE id = owner_user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'workflow_permissions') THEN
    UPDATE workflow_permissions SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'todos') THEN
    UPDATE todos SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tool_invocations') THEN
    UPDATE tool_invocations SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_secrets') THEN
    UPDATE user_secrets SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'secret_upload_otps') THEN
    UPDATE secret_upload_otps SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_kb_notes') THEN
    UPDATE user_kb_notes SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rag_documents') THEN
    UPDATE rag_documents SET user_id = (SELECT uuid::text FROM users WHERE id = user_id::bigint);
END IF; END $$;

-- 6. Switch primary key
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey CASCADE;
ALTER TABLE users DROP COLUMN IF EXISTS id;
ALTER TABLE users RENAME COLUMN uuid TO id;
ALTER TABLE users ADD PRIMARY KEY (id);

-- 7. Convert all foreign key columns to UUID (only if table exists)
ALTER TABLE IF EXISTS refresh_tokens ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS api_keys ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS workflows ALTER COLUMN owner_user_id TYPE UUID USING owner_user_id::uuid;
ALTER TABLE IF EXISTS workflow_permissions ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS todos ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS tool_invocations ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS user_secrets ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS secret_upload_otps ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS user_kb_notes ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
ALTER TABLE IF EXISTS rag_documents ALTER COLUMN user_id TYPE UUID USING user_id::uuid;

-- 8. Restore foreign keys (only add if table exists)
ALTER TABLE IF EXISTS refresh_tokens ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS api_keys ADD CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS workflows ADD CONSTRAINT workflows_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS workflow_permissions ADD CONSTRAINT workflow_permissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS todos ADD CONSTRAINT todos_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS tool_invocations ADD CONSTRAINT tool_invocations_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS user_secrets ADD CONSTRAINT user_secrets_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS secret_upload_otps ADD CONSTRAINT secret_upload_otps_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS user_kb_notes ADD CONSTRAINT user_kb_notes_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS rag_documents ADD CONSTRAINT rag_documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
