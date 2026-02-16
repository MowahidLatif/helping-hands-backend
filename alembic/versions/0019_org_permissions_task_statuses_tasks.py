"""org_user_permissions, task_statuses, campaign_tasks

Revision ID: 0019_org_permissions_tasks
Revises: 0018_campaign_page_layout
Create Date: 2025-02-16

"""

from alembic import op

revision = "0019_org_permissions_tasks"
down_revision = "0018_campaign_page_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS org_user_permissions (
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          permission TEXT NOT NULL,
          PRIMARY KEY (org_id, user_id, permission)
        );
        CREATE INDEX IF NOT EXISTS idx_org_user_permissions_org_user
          ON org_user_permissions(org_id, user_id);

        CREATE TABLE IF NOT EXISTS task_statuses (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          sort_order INT NOT NULL DEFAULT 0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_task_statuses_org ON task_statuses(org_id);

        CREATE TABLE IF NOT EXISTS campaign_tasks (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
          title TEXT NOT NULL,
          description TEXT NULL,
          assignee_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          status_id UUID NULL REFERENCES task_statuses(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_campaign_tasks_campaign ON campaign_tasks(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_campaign_tasks_assignee ON campaign_tasks(assignee_user_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS campaign_tasks")
    op.execute("DROP TABLE IF EXISTS task_statuses")
    op.execute("DROP TABLE IF EXISTS org_user_permissions")
