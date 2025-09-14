from alembic import op

revision = "0002_campaigns"
down_revision = "0001_auth_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'campaign_status') THEN
        CREATE TYPE campaign_status AS ENUM ('draft','active','paused','completed','archived');
      END IF;
    END$$;

    CREATE TABLE IF NOT EXISTS campaigns (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      slug TEXT NOT NULL,
      goal NUMERIC(12,2) NOT NULL DEFAULT 0,
      status campaign_status NOT NULL DEFAULT 'draft',
      custom_domain TEXT NULL,
      total_raised NUMERIC(12,2) NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (org_id, slug)
    );

    CREATE INDEX IF NOT EXISTS idx_campaigns_org ON campaigns(org_id);

    -- custom domains must be globally unique, but many rows will be NULL
    CREATE UNIQUE INDEX IF NOT EXISTS ux_campaigns_custom_domain
      ON campaigns(custom_domain)
      WHERE custom_domain IS NOT NULL;
    """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS campaigns;
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'campaign_status') THEN
        DROP TYPE campaign_status;
      END IF;
    END$$;
    """
    )
