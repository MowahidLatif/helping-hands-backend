"""users totp_secret and totp_enabled for TOTP 2FA

Revision ID: 0021_totp_2fa
Revises: 0020_anonymized_at
Create Date: 2025-02-18

"""

from alembic import op

revision = "0021_totp_2fa"
down_revision = "0020_anonymized_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT NULL;")
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT false;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS totp_enabled")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS totp_secret")
