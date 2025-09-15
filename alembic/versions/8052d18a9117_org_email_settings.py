# alembic/versions/<rev>_org_email_settings.py
from alembic import op

# IDs
revision = "0010_org_email_settings"
down_revision = "0009_email_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS org_email_settings (
      org_id           uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
      from_name        text,
      from_email       text,
      reply_to         text,
      bcc_to           text,
      receipt_subject  text,
      receipt_text     text,
      receipt_html     text,
      created_at       timestamptz NOT NULL DEFAULT now(),
      updated_at       timestamptz NOT NULL DEFAULT now()
    );
    """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS org_email_settings;")
