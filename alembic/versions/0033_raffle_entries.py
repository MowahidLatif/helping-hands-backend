"""Add raffle_entries table and winner FK on raffles

Revision ID: 0033_raffle_entries
Revises: 0032_raffles_table
"""

from alembic import op
import sqlalchemy as sa

revision = "0033_raffle_entries"
down_revision = "0032_raffles_table"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "raffle_entries",
        sa.Column("id", sa.Text(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("raffle_id", sa.Text(), nullable=False),
        sa.Column("donor_email", sa.String(320), nullable=False),
        sa.Column("donor_first_name", sa.String(100), nullable=True),
        sa.Column("donor_last_name", sa.String(100), nullable=True),
        sa.Column("display_consent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("source", sa.String(20), nullable=False, server_default="donation"),
        sa.Column("donation_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["raffle_id"], ["raffles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["donation_id"], ["donations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("raffle_id", "donor_email", name="uq_raffle_entries_raffle_email"),
    )
    op.create_index("ix_raffle_entries_raffle_id", "raffle_entries", ["raffle_id"])
    op.create_index("ix_raffle_entries_donor_email", "raffle_entries", ["donor_email"])

    # Add the winner FK on raffles now that raffle_entries exists
    op.create_foreign_key(
        "fk_raffles_winner_entry_id",
        "raffles",
        "raffle_entries",
        ["winner_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_raffles_winner_entry_id", "raffles", type_="foreignkey")
    op.drop_index("ix_raffle_entries_donor_email", table_name="raffle_entries")
    op.drop_index("ix_raffle_entries_raffle_id", table_name="raffle_entries")
    op.drop_table("raffle_entries")
