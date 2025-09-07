from alembic import op

revision = "0003_campaigns_constraints"
down_revision = "0002_campaigns"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname='campaigns' AND c.conname='ux_campaigns_org_slug'
      ) THEN
        ALTER TABLE campaigns
          ADD CONSTRAINT ux_campaigns_org_slug UNIQUE (org_id, slug);
      END IF;
    END$$;

    CREATE UNIQUE INDEX IF NOT EXISTS ux_campaigns_custom_domain
      ON campaigns(custom_domain)
      WHERE custom_domain IS NOT NULL;

    CREATE INDEX IF NOT EXISTS idx_campaigns_org
      ON campaigns(org_id);
    """
    )


def downgrade():
    op.execute(
        """
    DROP INDEX IF EXISTS idx_campaigns_org;
    DROP INDEX IF EXISTS ux_campaigns_custom_domain;
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname='campaigns' AND c.conname='ux_campaigns_org_slug'
      ) THEN
        ALTER TABLE campaigns
          DROP CONSTRAINT ux_campaigns_org_slug;
      END IF;
    END$$;
    """
    )
