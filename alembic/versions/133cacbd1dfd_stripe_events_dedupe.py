from alembic import op
import sqlalchemy as sa

revision = "0008_stripe_events"
down_revision = "0007_giveaway_logs"


def upgrade():
    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("raw", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("stripe_events")
