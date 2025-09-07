# alembic/versions/<new>_drop_dup_org_slug.py
from alembic import op

revision = "0004_drop_dup_org_slug"
down_revision = "0003_campaigns_constraints"


def upgrade():
    op.execute("ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS ux_campaigns_org_slug;")


def downgrade():
    op.execute(
        "ALTER TABLE campaigns ADD CONSTRAINT ux_campaigns_org_slug UNIQUE (org_id, slug);"
    )
