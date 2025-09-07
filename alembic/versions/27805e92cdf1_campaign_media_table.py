from alembic import op

revision = "0005_campaign_media"
down_revision = "0004_drop_dup_org_slug"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'media_type') THEN
        CREATE TYPE media_type AS ENUM ('image','video','doc','other');
      END IF;
    END$$;

    CREATE TABLE IF NOT EXISTS campaign_media (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
      campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
      type media_type NOT NULL,
      s3_key TEXT NOT NULL,
      content_type TEXT NULL,
      size_bytes BIGINT NULL,
      url TEXT NULL,           -- convenience for dev; prod can use presigned GET
      description TEXT NULL,
      sort INTEGER NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE UNIQUE INDEX IF NOT EXISTS ux_campaign_media_org_key ON campaign_media(org_id, s3_key);
    CREATE INDEX IF NOT EXISTS idx_campaign_media_campaign_sort ON campaign_media(campaign_id, sort);
    """
    )


def downgrade():
    op.execute(
        """
    DROP TABLE IF EXISTS campaign_media;
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'media_type') THEN
        DROP TYPE media_type;
      END IF;
    END$$;
    """
    )
