"""Raffle Part 2 schema: prize_value_cents, voiding columns, ends_at, void_redraws, claim_token_used_at

Revision ID: 0036_raffle_part2_schema
Revises: 0035_donations_add_name_fields
"""

from alembic import op
import sqlalchemy as sa

revision = "0036_raffle_part2_schema"
down_revision = "0035_donations_add_name_fields"
branch_labels = None
depends_on = None


def upgrade():
    # raffles table additions
    op.add_column("raffles", sa.Column("prize_value_cents", sa.Integer(), nullable=True))
    op.add_column("raffles", sa.Column("void_redraws", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("raffles", sa.Column("claim_token_used_at", sa.TIMESTAMP(timezone=True), nullable=True))

    # raffle_entries voiding columns
    op.add_column("raffle_entries", sa.Column("voided", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("raffle_entries", sa.Column("voided_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("raffle_entries", sa.Column("void_reason", sa.String(20), nullable=True))

    # campaigns: add optional ends_at for end-date locking and countdown timer
    op.add_column("campaigns", sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade():
    op.drop_column("campaigns", "ends_at")
    op.drop_column("raffle_entries", "void_reason")
    op.drop_column("raffle_entries", "voided_at")
    op.drop_column("raffle_entries", "voided")
    op.drop_column("raffles", "claim_token_used_at")
    op.drop_column("raffles", "void_redraws")
    op.drop_column("raffles", "prize_value_cents")
