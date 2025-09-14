from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_email_receipts"
down_revision = "0008_stripe_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # email_receipts table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS email_receipts (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            donation_id         uuid NOT NULL UNIQUE,
            to_email            text NOT NULL,
            subject             text NOT NULL,
            body_text           text NOT NULL,
            body_html           text,
            provider            text,
            provider_msg_id     text,
            sent_at             timestamptz,
            last_error          text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        );
    """
    )

    # touch function + trigger
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_email_receipts_touch()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_email_receipts_touch ON email_receipts;
        CREATE TRIGGER trg_email_receipts_touch
        BEFORE UPDATE ON email_receipts
        FOR EACH ROW EXECUTE FUNCTION trg_email_receipts_touch();
    """
    )

    # optional view for quick ops
    op.execute(
        """
        CREATE OR REPLACE VIEW v_stripe_events AS
        SELECT event_id, type, created_at, raw
        FROM stripe_events
        ORDER BY created_at DESC;
    """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_stripe_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_email_receipts_touch ON email_receipts;")
    op.execute("DROP FUNCTION IF EXISTS trg_email_receipts_touch();")
    op.execute("DROP TABLE IF EXISTS email_receipts;")
