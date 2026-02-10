"""add platform fee columns to campaigns

Revision ID: 0016_campaign_platform_fee
Revises: 0015_donations_message
Create Date: 2025-02-02

"""

from alembic import op

revision = "0016_campaign_platform_fee"
down_revision = "0015_donations_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE campaigns
        ADD COLUMN IF NOT EXISTS platform_fee_cents INTEGER NULL,
        ADD COLUMN IF NOT EXISTS platform_fee_percent NUMERIC(5,2) NULL,
        ADD COLUMN IF NOT EXISTS platform_fee_recorded_at TIMESTAMPTZ NULL
    """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE campaigns
        DROP COLUMN IF EXISTS platform_fee_cents,
        DROP COLUMN IF EXISTS platform_fee_percent,
        DROP COLUMN IF EXISTS platform_fee_recorded_at
    """
    )
