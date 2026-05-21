"""Add waitlist table

Revision ID: 0028_waitlist_table
Revises: 0027_org_tier
"""

from alembic import op
import sqlalchemy as sa

revision = "0028_waitlist_table"
down_revision = "0027_org_tier"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "waitlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade():
    op.drop_table("waitlist")
