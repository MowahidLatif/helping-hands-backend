"""add message column to donations

Revision ID: 0015_donations_message
Revises: 0014_media_embed
Create Date: 2025-02-02

"""

from alembic import op

revision = "0015_donations_message"
down_revision = "0014_media_embed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE donations ADD COLUMN IF NOT EXISTS message TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE donations DROP COLUMN IF EXISTS message")
