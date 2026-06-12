"""Add donor_first_name and donor_last_name to donations table

Revision ID: 0035_donations_add_name_fields
Revises: 0034_raffle_draw_log
"""

from alembic import op
import sqlalchemy as sa

revision = "0035_donations_add_name_fields"
down_revision = "0034_raffle_draw_log"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("donations", sa.Column("donor_first_name", sa.String(100), nullable=True))
    op.add_column("donations", sa.Column("donor_last_name", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("donations", "donor_last_name")
    op.drop_column("donations", "donor_first_name")
