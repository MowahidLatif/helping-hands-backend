"""Add trial billing fields and billing_email_log

Revision ID: 0031_org_trial_billing
Revises: 0030_subscription_cancel_fields
"""

from alembic import op
import sqlalchemy as sa

revision = "0031_org_trial_billing"
down_revision = "0030_subscription_cancel_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column("billing_interval", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("payment_grace_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_table(
        "billing_email_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.Text(), nullable=False),
        sa.Column("email_type", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("org_id", "email_type", name="uq_billing_email_log_org_type"),
    )
    op.create_index("ix_billing_email_log_org_id", "billing_email_log", ["org_id"])


def downgrade():
    op.drop_index("ix_billing_email_log_org_id", table_name="billing_email_log")
    op.drop_table("billing_email_log")
    op.drop_column("organizations", "payment_grace_ends_at")
    op.drop_column("organizations", "trial_ends_at")
    op.drop_column("organizations", "billing_interval")
