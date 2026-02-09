"""add embed media type for YouTube/Vimeo

Revision ID: 0014_media_embed
Revises: 0013_comments_updates
Create Date: 2025-02-02

"""

from alembic import op

revision = "0014_media_embed"
down_revision = "0013_comments_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE media_type ADD VALUE 'embed'")
    op.execute("ALTER TABLE campaign_media ALTER COLUMN s3_key DROP NOT NULL")
    # embed rows use url, s3_key can be NULL; relax unique for nullable s3_key
    op.execute("DROP INDEX IF EXISTS ux_campaign_media_org_key")
    op.execute(
        "CREATE UNIQUE INDEX ux_campaign_media_org_key "
        "ON campaign_media(org_id, s3_key) WHERE s3_key IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DELETE FROM campaign_media WHERE type = 'embed'")
    op.execute("ALTER TABLE campaign_media ALTER COLUMN s3_key SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS ux_campaign_media_org_key")
    op.execute(
        "CREATE UNIQUE INDEX ux_campaign_media_org_key "
        "ON campaign_media(org_id, s3_key)"
    )
    # Cannot remove enum value in PostgreSQL easily; leave 'embed' in type
