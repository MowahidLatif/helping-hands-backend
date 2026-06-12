"""Raffle Part 3 schema: min_entries, deletion_requested, triggered_by

Revision ID: 0039_raffle_part3_schema
Revises: 0038_orgs_timezone
"""

from alembic import op

revision = "0039_raffle_part3_schema"
down_revision = "0038_orgs_timezone"
branch_labels = None
depends_on = None


def upgrade():
    # Scale-only minimum entry threshold
    op.execute("ALTER TABLE raffles ADD COLUMN min_entries INTEGER")

    # GDPR/PIPEDA deletion-request hold flag on entries
    op.execute("""
        ALTER TABLE raffle_entries
        ADD COLUMN deletion_requested BOOLEAN NOT NULL DEFAULT false
    """)

    # Who triggered the draw (scheduler / sweep / org_manual / system_void)
    op.execute("ALTER TABLE raffle_draw_log ADD COLUMN triggered_by VARCHAR(20)")


def downgrade():
    op.execute("ALTER TABLE raffles DROP COLUMN IF EXISTS min_entries")
    op.execute("ALTER TABLE raffle_entries DROP COLUMN IF EXISTS deletion_requested")
    op.execute("ALTER TABLE raffle_draw_log DROP COLUMN IF EXISTS triggered_by")
