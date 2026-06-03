"""Add subscription cancel tracking fields to organizations

Revision ID: 0030_subscription_cancel_fields
Revises: 0029_org_billing
"""

from alembic import op
import sqlalchemy as sa

revision = "0030_subscription_cancel_fields"
down_revision = "0029_org_billing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column("subscription_cancel_at_period_end", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("subscription_cancel_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("organizations", "subscription_cancel_at")
    op.drop_column("organizations", "subscription_cancel_at_period_end")
