"""password_reset_tokens table for email-based forgot-password flow

Revision ID: 0022_password_reset_tokens
Revises: 0021_totp_2fa
Create Date: 2025-02-18

"""

from alembic import op

revision = "0022_password_reset_tokens"
down_revision = "0021_totp_2fa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          token_hash TEXT NOT NULL UNIQUE,
          expires_at TIMESTAMPTZ NOT NULL,
          used_at TIMESTAMPTZ NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_prt_user ON password_reset_tokens(user_id);
        CREATE INDEX IF NOT EXISTS idx_prt_hash ON password_reset_tokens(token_hash);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_reset_tokens;")
