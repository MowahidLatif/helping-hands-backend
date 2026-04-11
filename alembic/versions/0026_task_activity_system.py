"""task comments/activity system

Revision ID: 0026_task_activity_system
Revises: 0025_campaign_task_multi_assignees
"""

from alembic import op

revision = "0026_task_activity_system"
down_revision = "0025_campaign_task_multi_assignees"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS task_comments (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          task_id UUID NOT NULL REFERENCES campaign_tasks(id) ON DELETE CASCADE,
          campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          author_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          comment_type TEXT NOT NULL,
          body TEXT NULL,
          metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_task_comments_task_created
          ON task_comments(task_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS task_comment_mentions (
          comment_id UUID NOT NULL REFERENCES task_comments(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          PRIMARY KEY (comment_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS task_comment_reactions (
          comment_id UUID NOT NULL REFERENCES task_comments(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          reaction TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (comment_id, user_id, reaction)
        );

        CREATE TABLE IF NOT EXISTS task_checklist_items (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          task_id UUID NOT NULL REFERENCES campaign_tasks(id) ON DELETE CASCADE,
          campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          is_checked BOOLEAN NOT NULL DEFAULT FALSE,
          created_by_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          checked_by_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_task_checklist_task
          ON task_checklist_items(task_id, created_at);

        CREATE TABLE IF NOT EXISTS task_time_entries (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          task_id UUID NOT NULL REFERENCES campaign_tasks(id) ON DELETE CASCADE,
          campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          hours NUMERIC(6,2) NOT NULL,
          note TEXT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_task_time_entries_task
          ON task_time_entries(task_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS task_notification_intents (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          task_id UUID NOT NULL REFERENCES campaign_tasks(id) ON DELETE CASCADE,
          comment_id UUID NULL REFERENCES task_comments(id) ON DELETE SET NULL,
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          recipient_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          event_type TEXT NOT NULL,
          channel TEXT NOT NULL DEFAULT 'email',
          status TEXT NOT NULL DEFAULT 'pending',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_task_notification_intents_recipient
          ON task_notification_intents(recipient_user_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_notification_intents;")
    op.execute("DROP TABLE IF EXISTS task_time_entries;")
    op.execute("DROP TABLE IF EXISTS task_checklist_items;")
    op.execute("DROP TABLE IF EXISTS task_comment_reactions;")
    op.execute("DROP TABLE IF EXISTS task_comment_mentions;")
    op.execute("DROP TABLE IF EXISTS task_comments;")
