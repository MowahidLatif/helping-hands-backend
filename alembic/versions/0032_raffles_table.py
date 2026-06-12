"""Add raffles table

Revision ID: 0032_raffles_table
Revises: 0031_org_trial_billing
"""

from alembic import op
import sqlalchemy as sa

revision = "0032_raffles_table"
down_revision = "0031_org_trial_billing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "raffles",
        sa.Column("id", sa.Text(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("campaign_id", sa.Text(), nullable=False),
        sa.Column("prize_name", sa.String(120), nullable=False),
        sa.Column("prize_description", sa.Text(), nullable=True),
        sa.Column("prize_image_url", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("winner_entry_id", sa.Text(), nullable=True),
        sa.Column("redraw_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_redraws", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("claim_deadline", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("compliance_ack_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("campaign_id", name="uq_raffles_campaign_id"),
    )
    op.create_index("ix_raffles_campaign_id", "raffles", ["campaign_id"])
    op.create_index("ix_raffles_status", "raffles", ["status"])


def downgrade():
    op.drop_index("ix_raffles_status", table_name="raffles")
    op.drop_index("ix_raffles_campaign_id", table_name="raffles")
    op.drop_table("raffles")
