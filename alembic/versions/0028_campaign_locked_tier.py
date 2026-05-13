"""Lock org tier at campaign creation time

Revision ID: 0028_campaign_locked_tier
Revises: 0027_org_tier
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_campaign_locked_tier"
down_revision = "0027_org_tier"
branch_labels = None
depends_on = None


def upgrade():
    # locked_tier records the org's tier at campaign creation and never changes.
    # Existing campaigns default to 1 (Starter) since all existing orgs defaulted to 1.
    op.add_column(
        "campaigns",
        sa.Column(
            "locked_tier",
            sa.SmallInteger(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade():
    op.drop_column("campaigns", "locked_tier")
