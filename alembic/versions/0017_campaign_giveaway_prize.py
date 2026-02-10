"""add optional giveaway_prize_cents to campaigns

Revision ID: 0017_campaign_giveaway_prize
Revises: 0016_campaign_platform_fee
Create Date: 2025-02-02

"""

from alembic import op

revision = "0017_campaign_giveaway_prize"
down_revision = "0016_campaign_platform_fee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS giveaway_prize_cents INTEGER NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS giveaway_prize_cents")
