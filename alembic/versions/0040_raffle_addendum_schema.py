"""Raffle addendum schema: org/campaign currency, entry phone, draw log expire_reason

Revision ID: 0040_raffle_addendum_schema
Revises: 0039_raffle_part3_schema
"""

from alembic import op

revision = "0040_raffle_addendum_schema"
down_revision = "0039_raffle_part3_schema"
branch_labels = None
depends_on = None


def upgrade():
    # Org-level currency (ISO 4217, locked after first published campaign)
    op.execute(
        "ALTER TABLE organizations ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'usd'"
    )

    # Campaign currency stamped from org at creation time
    op.execute(
        "ALTER TABLE campaigns ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'usd'"
    )

    # Optional phone for raffle winner contact backup (E.164, no SMS this phase)
    op.execute("ALTER TABLE raffle_entries ADD COLUMN phone VARCHAR(20)")

    # Why the claim window expired: 'deadline' (48h) or 'bounced' (SendGrid hard-bounce)
    op.execute("ALTER TABLE raffle_draw_log ADD COLUMN expire_reason VARCHAR(20)")


def downgrade():
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE raffle_entries DROP COLUMN IF EXISTS phone")
    op.execute("ALTER TABLE raffle_draw_log DROP COLUMN IF EXISTS expire_reason")
