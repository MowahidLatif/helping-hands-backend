"""Backfill campaigns.locked_tier from org tier, then add NOT NULL constraint

Revision ID: 0037_backfill_locked_tier
Revises: 0036_raffle_part2_schema
"""

from alembic import op

revision = "0037_backfill_locked_tier"
down_revision = "0036_raffle_part2_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE campaigns
        SET locked_tier = (
            SELECT tier FROM organizations WHERE organizations.id = campaigns.org_id
        )
        WHERE locked_tier IS NULL
    """)
    op.execute("ALTER TABLE campaigns ALTER COLUMN locked_tier SET NOT NULL")
    op.execute("ALTER TABLE campaigns ALTER COLUMN locked_tier SET DEFAULT 1")


def downgrade():
    op.execute("ALTER TABLE campaigns ALTER COLUMN locked_tier DROP NOT NULL")
    op.execute("ALTER TABLE campaigns ALTER COLUMN locked_tier DROP DEFAULT")
