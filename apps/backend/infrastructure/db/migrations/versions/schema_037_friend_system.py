"""
Friendship System: friend_requests + friends tables
"""

from __future__ import annotations

from alembic import op

revision = "schema_037"
down_revision = "schema_036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS friend_requests (
          id BIGSERIAL PRIMARY KEY,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          from_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          to_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'pending',
          message TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          responded_at TIMESTAMPTZ,
          UNIQUE (from_user_id, to_user_id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_friend_requests_from
          ON friend_requests (from_user_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_friend_requests_to
          ON friend_requests (to_user_id, created_at DESC);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS friends (
          id BIGSERIAL PRIMARY KEY,
          tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          friend_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          relation TEXT,
          note TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (user_id, friend_user_id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_friends_user
          ON friends (user_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_friends_friend
          ON friends (friend_user_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS friends CASCADE;")
    op.execute("DROP TABLE IF EXISTS friend_requests CASCADE;")