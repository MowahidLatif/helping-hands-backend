"""add thank_you and winner email template columns to org_email_settings

Revision ID: 0012_thank_you_winner
Revises: 0011_subdomain_slug
Create Date: 2025-02-02

"""

from alembic import op

revision = "0012_thank_you_winner"
down_revision = "0011_subdomain_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in (
        "thank_you_subject",
        "thank_you_text",
        "thank_you_html",
        "winner_subject",
        "winner_text",
        "winner_html",
    ):
        op.execute(
            f"ALTER TABLE org_email_settings ADD COLUMN IF NOT EXISTS {col} text;"
        )


def downgrade() -> None:
    for col in (
        "thank_you_subject",
        "thank_you_text",
        "thank_you_html",
        "winner_subject",
        "winner_text",
        "winner_html",
    ):
        op.execute(f"ALTER TABLE org_email_settings DROP COLUMN IF EXISTS {col};")
