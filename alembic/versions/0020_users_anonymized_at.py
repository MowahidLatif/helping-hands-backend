"""users anonymized_at for account deletion (anonymize, no hard delete)

Revision ID: 0020_anonymized_at
Revises: 0019_org_permissions_tasks
Create Date: 2025-02-18

"""

from alembic import op

revision = "0020_anonymized_at"
down_revision = "0019_org_permissions_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS anonymized_at TIMESTAMPTZ NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS anonymized_at;")
