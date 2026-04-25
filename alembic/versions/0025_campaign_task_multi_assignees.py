"""campaign task multi assignees

Revision ID: 0025_campaign_task_multi_assignees
Revises: 0024_fee_policy_settlements
"""

from alembic import op

revision = "0025_task_multi_assignees"
down_revision = "0024_fee_policy_settlements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_task_assignees (
          task_id UUID NOT NULL REFERENCES campaign_tasks(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          assigned_by_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
          PRIMARY KEY (task_id, user_id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_campaign_task_assignees_user
        ON campaign_task_assignees(user_id, assigned_at DESC);
        """
    )
    op.execute(
        """
        INSERT INTO campaign_task_assignees (task_id, user_id)
        SELECT id, assignee_user_id
        FROM campaign_tasks
        WHERE assignee_user_id IS NOT NULL
        ON CONFLICT (task_id, user_id) DO NOTHING;
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_campaign_tasks_assignee;")
    op.execute("ALTER TABLE campaign_tasks DROP COLUMN IF EXISTS assignee_user_id;")


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE campaign_tasks
        ADD COLUMN IF NOT EXISTS assignee_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL;
        """
    )
    op.execute(
        """
        UPDATE campaign_tasks ct
        SET assignee_user_id = sq.user_id
        FROM (
          SELECT DISTINCT ON (task_id) task_id, user_id
          FROM campaign_task_assignees
          ORDER BY task_id, assigned_at ASC
        ) sq
        WHERE sq.task_id = ct.id;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_campaign_tasks_assignee
        ON campaign_tasks(assignee_user_id);
        """
    )
    op.execute("DROP TABLE IF EXISTS campaign_task_assignees;")
