from app.utils.db import get_db_connection
from typing import Any
from app.utils.slug import slugify, slugify_with_fallback


def insert_campaign(data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO campaigns (user_id, title, slug, description, goal_amount)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """,
        (
            data["user_id"],
            data["title"],
            data["slug"],
            data.get("description"),
            data.get("goal_amount"),
        ),
    )
    campaign = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return campaign


def select_campaigns():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM campaigns ORDER BY created_at DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def update_campaign_data(campaign_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE campaigns
        SET title = %s, description = %s, is_completed = %s, goal_amount = %s
        WHERE id = %s
        RETURNING *;
    """,
        (
            data["title"],
            data["description"],
            data["is_completed"],
            data["goal_amount"],
            campaign_id,
        ),
    )
    campaign = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return campaign


def delete_campaign_by_id(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM campaigns WHERE id = %s;", (campaign_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "deleted"}


def _slug_exists(org_id: str, slug: str) -> bool:
    sql = "SELECT 1 FROM campaigns WHERE org_id = %s AND slug = %s LIMIT 1"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, slug))
        return cur.fetchone() is not None


def unique_slug_for_org(org_id: str, base: str) -> str:
    base_slug = slugify_with_fallback(base, fallback="campaign")
    candidate = base_slug
    i = 2
    while _slug_exists(org_id, candidate):
        candidate = f"{base_slug}-{i}"
        i += 1
    return candidate


def create_campaign(
    org_id: str,
    title: str,
    goal: float = 0.0,
    status: str = "draft",
    custom_domain: str | None = None,
) -> dict[str, Any]:
    slug = unique_slug_for_org(org_id, title)
    sql = """
    INSERT INTO campaigns (org_id, title, slug, goal, status, custom_domain)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id, org_id, title, slug, goal, status, custom_domain, total_raised, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, title, slug, goal, status, custom_domain))
        row = cur.fetchone()
        conn.commit()
        cols = [
            "id",
            "org_id",
            "title",
            "slug",
            "goal",
            "status",
            "custom_domain",
            "total_raised",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    sql = "SELECT id, org_id, title, slug, goal, status, custom_domain, total_raised, created_at, updated_at FROM campaigns WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [
            "id",
            "org_id",
            "title",
            "slug",
            "goal",
            "status",
            "custom_domain",
            "total_raised",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def list_campaigns(org_id: str) -> list[dict[str, Any]]:
    sql = """
    SELECT id, org_id, title, slug, goal, status, custom_domain, total_raised, created_at, updated_at
    FROM campaigns
    WHERE org_id = %s
    ORDER BY created_at DESC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        rows = cur.fetchall()
        cols = [
            "id",
            "org_id",
            "title",
            "slug",
            "goal",
            "status",
            "custom_domain",
            "total_raised",
            "created_at",
            "updated_at",
        ]
        return [dict(zip(cols, r)) for r in rows]


def update_campaign(
    campaign_id: str,
    *,
    title: str | None = None,
    goal: float | None = None,
    status: str | None = None,
    slug: str | None = None,
    custom_domain: str | None = None,
) -> dict[str, Any] | None:
    sets, params = [], []
    if title is not None:
        sets.append("title = %s")
        params.append(title)
    if goal is not None:
        sets.append("goal = %s")
        params.append(goal)
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if slug is not None:
        sets.append("slug = %s")
        params.append(slugify(slug))
    if custom_domain is not None:
        sets.append("custom_domain = %s")
        params.append(custom_domain)
    if not sets:
        return get_campaign(campaign_id)
    sets.append("updated_at = now()")
    sql = f"UPDATE campaigns SET {', '.join(sets)} WHERE id = %s RETURNING id, org_id, title, slug, goal, status, custom_domain, total_raised, created_at, updated_at"
    params.append(campaign_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        cols = [
            "id",
            "org_id",
            "title",
            "slug",
            "goal",
            "status",
            "custom_domain",
            "total_raised",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def delete_campaign(campaign_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))
        conn.commit()
        return cur.rowcount > 0


def recompute_total_raised(campaign_id: str) -> dict[str, Any]:
    """
    Sets campaigns.total_raised to SUM(donations.amount_cents where succeeded) / 100.
    Returns {"total_raised": Decimal(...)}.
    """
    sql = """
    UPDATE campaigns
    SET total_raised = (
      SELECT COALESCE(SUM(amount_cents),0) / 100.0
      FROM donations
      WHERE campaign_id = %s AND status = 'succeeded'
    )::numeric(12,2),
    updated_at = now()
    WHERE id = %s
    RETURNING total_raised
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, campaign_id))
        row = cur.fetchone()
        conn.commit()
        return {"total_raised": row[0]}


def get_goal_and_total(campaign_id: str) -> tuple[float, float] | None:
    sql = "SELECT goal, total_raised FROM campaigns WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        if not row:
            return None
        return (float(row[0]), float(row[1]))


def get_campaign_by_id(campaign_id: str) -> dict[str, Any] | None:
    return get_campaign(campaign_id)


def insert_giveaway_log(
    *,
    org_id: str,
    campaign_id: str,
    winner_donation_id: str | None,
    created_by_user_id: str,
    mode: str,
    population_count: int,
    population_hash: str,
    notes: str | None = None,
) -> dict[str, Any]:
    sql = """
    INSERT INTO giveaway_logs (
        org_id,
        campaign_id,
        winner_donation_id,
        created_by_user_id,
        mode,
        population_count,
        population_hash,
        notes
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING
        id, org_id, campaign_id, winner_donation_id,
        created_by_user_id, mode, population_count, population_hash, notes, created_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                org_id,
                campaign_id,
                winner_donation_id,
                created_by_user_id,
                mode,
                population_count,
                population_hash,
                notes,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "winner_donation_id",
            "created_by_user_id",
            "mode",
            "population_count",
            "population_hash",
            "notes",
            "created_at",
        ]
        return dict(zip(cols, row))


def list_giveaway_logs(campaign_id: str, limit: int = 20) -> list[dict]:
    sql = """
      SELECT campaign_id, winner_donation_id, mode, population_count, created_at
      FROM giveaway_logs
      WHERE campaign_id = %s
      ORDER BY created_at DESC
      LIMIT %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, limit))
        rows = cur.fetchall()
        cols = [
            "campaign_id",
            "winner_donation_id",
            "mode",
            "population_count",
            "created_at",
        ]
        return [dict(zip(cols, r)) for r in rows]
