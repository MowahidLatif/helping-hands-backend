"""campaign_comments and campaign_updates tables

Revision ID: 0013_comments_updates
Revises: 0012_thank_you_winner
Create Date: 2025-02-02

"""

from alembic import op

revision = "0013_comments_updates"
down_revision = "0012_thank_you_winner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_campaign_comments_campaign
            ON campaign_comments(campaign_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS campaign_updates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            author_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_campaign_updates_campaign
            ON campaign_updates(campaign_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS campaign_comments;")
    op.execute("DROP TABLE IF EXISTS campaign_updates;")
