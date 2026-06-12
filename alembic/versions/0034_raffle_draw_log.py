"""Add raffle_draw_log table

Revision ID: 0034_raffle_draw_log
Revises: 0033_raffle_entries
"""

from alembic import op
import sqlalchemy as sa

revision = "0034_raffle_draw_log"
down_revision = "0033_raffle_entries"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "raffle_draw_log",
        sa.Column("id", sa.Text(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("raffle_id", sa.Text(), nullable=False),
        sa.Column("entry_id", sa.Text(), nullable=False),
        sa.Column("drawn_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="notified"),
        sa.Column("notified_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["raffle_id"], ["raffles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["raffle_entries.id"]),
    )
    op.create_index("ix_raffle_draw_log_raffle_id", "raffle_draw_log", ["raffle_id"])
    op.create_index("ix_raffle_draw_log_outcome", "raffle_draw_log", ["outcome"])


def downgrade():
    op.drop_index("ix_raffle_draw_log_outcome", table_name="raffle_draw_log")
    op.drop_index("ix_raffle_draw_log_raffle_id", table_name="raffle_draw_log")
    op.drop_table("raffle_draw_log")
