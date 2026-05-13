"""Add tier column to organizations

Revision ID: 0027_org_tier
Revises: 0026_task_activity_system
"""

from alembic import op
import sqlalchemy as sa

revision = "0027_org_tier"
down_revision = "0026_task_activity_system"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column(
            "tier",
            sa.SmallInteger(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade():
    op.drop_column("organizations", "tier")
