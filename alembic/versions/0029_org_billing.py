"""Add Stripe Billing fields to organizations

Revision ID: 0029_org_billing
Revises: 0028_campaign_locked_tier
"""

from alembic import op
import sqlalchemy as sa

revision = "0029_org_billing"
down_revision = "0028_campaign_locked_tier"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "subscription_status",
            sa.Text(),
            nullable=False,
            server_default="legacy",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column("subscription_current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("pending_tier", sa.SmallInteger(), nullable=True),
    )


def downgrade():
    op.drop_column("organizations", "pending_tier")
    op.drop_column("organizations", "subscription_current_period_end")
    op.drop_column("organizations", "subscription_status")
    op.drop_column("organizations", "stripe_subscription_id")
    op.drop_column("organizations", "stripe_customer_id")
