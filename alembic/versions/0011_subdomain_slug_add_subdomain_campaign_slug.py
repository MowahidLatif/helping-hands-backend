from alembic import op
from sqlalchemy.sql import text

revision = "0011_subdomain_slug"
down_revision = "0010_org_email_settings"
branch_labels = None
depends_on = None


def _slugify_sql(expr: str) -> str:
    # lowercase, replace non-alnum with '-', trim '-'
    return f"trim(both '-' from regexp_replace(lower({expr}), '[^a-z0-9]+', '-', 'g'))"


def upgrade():
    conn = op.get_bind()

    # ---------- 1) organizations.subdomain ----------
    # add column (safe if already there)
    op.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS subdomain TEXT")

    # ensure subdomain values for rows that are still NULL
    rows = conn.execute(
        text("SELECT id, name FROM organizations WHERE subdomain IS NULL")
    ).fetchall()
    for org_id, name in rows:
        slug_row = conn.execute(
            text(f"SELECT {_slugify_sql(':name')} AS s"), {"name": name or ""}
        ).fetchone()
        s = (slug_row[0] or "").strip("-")
        if not s or s.isnumeric():
            s = f"org-{org_id}"

        base = s
        i = 2
        while True:
            exists = conn.execute(
                text("SELECT 1 FROM organizations WHERE subdomain=:s AND id<>:id"),
                {"s": s, "id": org_id},
            ).fetchone()
            if not exists:
                break
            s = f"{base}-{i}"
            i += 1

        conn.execute(
            text("UPDATE organizations SET subdomain=:s WHERE id=:id"),
            {"s": s, "id": org_id},
        )

    # unique index for subdomain (idempotent)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_organizations_subdomain ON organizations(subdomain)"
    )

    # set NOT NULL (will succeed only after backfill)
    op.execute("ALTER TABLE organizations ALTER COLUMN subdomain SET NOT NULL")

    # ---------- 2) campaigns.slug ----------
    # add column (safe if already there)
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS slug TEXT")

    # backfill only where missing/empty
    rows = conn.execute(
        text("SELECT id, org_id, title FROM campaigns WHERE slug IS NULL OR slug=''")
    ).fetchall()
    for cid, org_id, title in rows:
        slug_row = conn.execute(
            text(f"SELECT {_slugify_sql(':title')} AS s"), {"title": title or ""}
        ).fetchone()
        s = (slug_row[0] or "").strip("-")
        if not s or s.isnumeric():
            s = f"campaign-{cid}"

        base = s
        i = 2
        while True:
            exists = conn.execute(
                text(
                    "SELECT 1 FROM campaigns WHERE org_id=:org AND slug=:s AND id<>:cid"
                ),
                {"org": org_id, "s": s, "cid": cid},
            ).fetchone()
            if not exists:
                break
            s = f"{base}-{i}"
            i += 1

        conn.execute(
            text("UPDATE campaigns SET slug=:s WHERE id=:cid"),
            {"s": s, "cid": cid},
        )

    # unique index for (org_id, slug) (idempotent)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_campaigns_org_slug ON campaigns(org_id, slug)"
    )

    # set NOT NULL
    op.execute("ALTER TABLE campaigns ALTER COLUMN slug SET NOT NULL")


def downgrade():
    # campaigns
    op.execute("DROP INDEX IF EXISTS uq_campaigns_org_slug")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS slug")

    # organizations
    op.execute("DROP INDEX IF EXISTS uq_organizations_subdomain")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS subdomain")
