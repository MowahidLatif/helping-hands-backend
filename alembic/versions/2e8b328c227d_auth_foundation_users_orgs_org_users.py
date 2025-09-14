from alembic import op

revision = "0001_auth_foundation"
down_revision = "7079d9406537"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    -- Required extensions
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    CREATE EXTENSION IF NOT EXISTS "citext";

    -- Role enum
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'org_user_role') THEN
        CREATE TYPE org_user_role AS ENUM ('owner','admin','member');
      END IF;
    END$$;

    -- Organizations
    CREATE TABLE IF NOT EXISTS organizations (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      name TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- Users
    CREATE TABLE IF NOT EXISTS users (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      email CITEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      name TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- Org memberships
    CREATE TABLE IF NOT EXISTS org_users (
      org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role org_user_role NOT NULL DEFAULT 'owner',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (org_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_org_users_user_id ON org_users(user_id);
    """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS org_users;
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS organizations;
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'org_user_role') THEN
        DROP TYPE org_user_role;
      END IF;
    END$$;
    """
    )


# """auth foundation (users, orgs, org_users)

# Revision ID: 2e8b328c227d
# Revises: 7079d9406537
# Create Date: 2025-09-03 18:48:33.045907

# """
# from typing import Sequence, Union

# from alembic import op
# import sqlalchemy as sa


# # revision identifiers, used by Alembic.
# revision: str = '2e8b328c227d'
# down_revision: Union[str, Sequence[str], None] = '7079d9406537'
# branch_labels: Union[str, Sequence[str], None] = None
# depends_on: Union[str, Sequence[str], None] = None


# def upgrade() -> None:
#     """Upgrade schema."""
#     pass


# def downgrade() -> None:
#     """Downgrade schema."""
#     pass
