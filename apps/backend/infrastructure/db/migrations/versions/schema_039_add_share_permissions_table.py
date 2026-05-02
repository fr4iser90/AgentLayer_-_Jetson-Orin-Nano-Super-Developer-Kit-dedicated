"""
Add share_permissions table for granular friend access control
"""

from __future__ import annotations

from alembic import op

revision = "schema_039"
down_revision = "schema_038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS share_permissions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_user_id UUID NOT NULL,
            grantee_user_id UUID NOT NULL,
            resource_type TEXT NOT NULL,
            resource_identifier TEXT NOT NULL,
            is_allowed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ NULL
        );
        """
    )
    
    # Note: PostgreSQL does not support IF NOT EXISTS for ADD CONSTRAINT
    # We check existence manually instead
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_share_permission_unique') THEN
                ALTER TABLE share_permissions
                ADD CONSTRAINT uq_share_permission_unique
                UNIQUE (owner_user_id, grantee_user_id, resource_type, resource_identifier);
            END IF;
        END $$;
        """
    )
    
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_share_permissions_owner
        ON share_permissions (owner_user_id);
        """
    )
    
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_share_permissions_grantee
        ON share_permissions (grantee_user_id);
        """
    )
    
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_share_permissions_resource
        ON share_permissions (resource_type, resource_identifier);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_share_permissions_resource;
        """
    )
    
    op.execute(
        """
        DROP INDEX IF EXISTS idx_share_permissions_grantee;
        """
    )
    
    op.execute(
        """
        DROP INDEX IF EXISTS idx_share_permissions_owner;
        """
    )
    
    op.execute(
        """
        ALTER TABLE share_permissions
        DROP CONSTRAINT IF EXISTS uq_share_permission_unique;
        """
    )
    
    op.execute(
        """
        DROP TABLE IF EXISTS share_permissions;
        """
    )