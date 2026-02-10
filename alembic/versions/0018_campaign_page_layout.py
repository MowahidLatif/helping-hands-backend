"""add page_layout JSONB to campaigns

Revision ID: 0018_campaign_page_layout
Revises: 0017_campaign_giveaway_prize
Create Date: 2025-02-02

"""

from alembic import op

revision = "0018_campaign_page_layout"
down_revision = "0017_campaign_giveaway_prize"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE campaigns
        ADD COLUMN IF NOT EXISTS page_layout JSONB NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS page_layout")
