from alembic import op

revision = "0006_donations"
down_revision = "0005_campaign_media"  # <- your last head
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'donation_status') THEN
        CREATE TYPE donation_status AS ENUM (
          'initiated','requires_payment','processing','succeeded','failed','refunded','canceled'
        );
      END IF;
    END$$;

    CREATE TABLE IF NOT EXISTS donations (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
      campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
      amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
      currency TEXT NOT NULL DEFAULT 'usd',
      donor_email CITEXT NULL,
      status donation_status NOT NULL DEFAULT 'initiated',
      stripe_payment_intent_id TEXT UNIQUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_donations_campaign ON donations(campaign_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_donations_org      ON donations(org_id, created_at);
    """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS donations;
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'donation_status') THEN
        DROP TYPE donation_status;
      END IF;
    END$$;
    """
    )
