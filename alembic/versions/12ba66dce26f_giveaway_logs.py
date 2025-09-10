from alembic import op

# keep your sequence aligned with your chain
revision = "0007_giveaway_logs"
down_revision = "0006_donations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS giveaway_logs (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
      campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
      winner_donation_id UUID NOT NULL REFERENCES donations(id),
      winner_email CITEXT,
      mode TEXT NOT NULL DEFAULT 'per_donation',      -- 'per_donation' | 'per_donor'
      population_count INTEGER NOT NULL,
      population_hash TEXT NOT NULL,                  -- sha256 of population & params
      created_by_user_id UUID NOT NULL REFERENCES users(id),
      notes TEXT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_giveaway_campaign ON giveaway_logs (campaign_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_giveaway_org ON giveaway_logs (org_id, created_at DESC);
    """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS giveaway_logs;")
