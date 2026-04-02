"""ai_site_recipe on campaigns + ai_generation_jobs

Revision ID: 0023_ai_site_recipe
Revises: 0022_password_reset_tokens
"""

from alembic import op

revision = "0023_ai_site_recipe"
down_revision = "0022_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE campaigns
        ADD COLUMN IF NOT EXISTS ai_site_recipe JSONB NULL;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_generation_jobs (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
          created_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          status TEXT NOT NULL DEFAULT 'pending',
          step TEXT NULL,
          progress_percent INT NOT NULL DEFAULT 0,
          error_message TEXT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ai_generation_jobs_campaign_id
        ON ai_generation_jobs (campaign_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ai_generation_jobs_campaign_id;")
    op.execute("DROP TABLE IF EXISTS ai_generation_jobs;")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS ai_site_recipe;")
