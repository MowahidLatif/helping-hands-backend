"""Add timezone column to organizations

Revision ID: 0038_orgs_timezone
Revises: 0037_backfill_locked_tier
"""

from alembic import op

revision = "0038_orgs_timezone"
down_revision = "0037_backfill_locked_tier"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE organizations
        ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'
    """)


def downgrade():
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS timezone")
