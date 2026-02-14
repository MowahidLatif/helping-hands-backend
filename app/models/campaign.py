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
    giveaway_prize_cents: int | None = None,
) -> dict[str, Any]:
    slug = unique_slug_for_org(org_id, title)
    sql = """
    INSERT INTO campaigns (org_id, title, slug, goal, status, custom_domain, giveaway_prize_cents)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id, org_id, title, slug, goal, status, custom_domain, total_raised, giveaway_prize_cents, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (org_id, title, slug, goal, status, custom_domain, giveaway_prize_cents),
        )
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
            "giveaway_prize_cents",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    sql = """SELECT id, org_id, title, slug, goal, status, custom_domain, total_raised,
             platform_fee_cents, platform_fee_percent, platform_fee_recorded_at,
             giveaway_prize_cents, page_layout, created_at, updated_at FROM campaigns WHERE id = %s"""
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
            "platform_fee_cents",
            "platform_fee_percent",
            "platform_fee_recorded_at",
            "giveaway_prize_cents",
            "page_layout",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def get_page_layout(campaign_id: str) -> dict[str, Any] | None:
    """Return page_layout for campaign, or None if not found."""
    sql = "SELECT page_layout FROM campaigns WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None


def set_page_layout(campaign_id: str, layout: dict[str, Any] | None) -> bool:
    """Set page_layout for campaign. Returns True if updated."""
    from psycopg2.extras import Json

    sql = "UPDATE campaigns SET page_layout = %s, updated_at = now() WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (Json(layout) if layout else None, campaign_id))
        conn.commit()
        return cur.rowcount > 0


def list_campaigns(
    org_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
    SELECT id, org_id, title, slug, goal, status, custom_domain, total_raised,
           platform_fee_cents, platform_fee_percent, platform_fee_recorded_at,
           giveaway_prize_cents, page_layout, created_at, updated_at
    FROM campaigns
    WHERE org_id = %s
    """
    params: list[Any] = [org_id]
    if status:
        valid = ("draft", "active", "paused", "completed", "archived")
        if status.lower() in valid:
            sql += " AND status = %s"
            params.append(status.lower())
    sql += " ORDER BY created_at DESC"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
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
            "platform_fee_cents",
            "platform_fee_percent",
            "platform_fee_recorded_at",
            "giveaway_prize_cents",
            "page_layout",
            "created_at",
            "updated_at",
        ]
        return [dict(zip(cols, r)) for r in rows]


def record_platform_fee_if_goal_reached(campaign_id: str) -> bool:
    """
    If campaign has reached its goal and no fee has been recorded yet,
    calculate and record the platform fee. Returns True if fee was recorded.
    """
    from app.utils.platform_fees import calculate_platform_fee

    sql = """SELECT goal, total_raised, platform_fee_recorded_at
             FROM campaigns WHERE id = %s"""
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        if not row:
            return False
        goal, total_raised, fee_recorded_at = float(row[0]), float(row[1]), row[2]
        if fee_recorded_at is not None or goal <= 0 or total_raised < goal:
            return False
        pct, _, fee_cents = calculate_platform_fee(total_raised)
        cur.execute(
            """UPDATE campaigns
               SET platform_fee_cents = %s, platform_fee_percent = %s,
                   platform_fee_recorded_at = now(), updated_at = now()
               WHERE id = %s""",
            (fee_cents, pct, campaign_id),
        )
        conn.commit()
        return cur.rowcount > 0


def update_campaign(
    campaign_id: str,
    *,
    title: str | None = None,
    goal: float | None = None,
    status: str | None = None,
    slug: str | None = None,
    custom_domain: str | None = None,
    giveaway_prize_cents: int | None = None,
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
    if giveaway_prize_cents is not None:
        sets.append("giveaway_prize_cents = %s")
        params.append(giveaway_prize_cents)
    if not sets:
        return get_campaign(campaign_id)
    sets.append("updated_at = now()")
    sql = f"UPDATE campaigns SET {', '.join(sets)} WHERE id = %s RETURNING id, org_id, title, slug, goal, status, custom_domain, total_raised, platform_fee_cents, platform_fee_percent, platform_fee_recorded_at, giveaway_prize_cents, page_layout, created_at, updated_at"
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
            "platform_fee_cents",
            "platform_fee_percent",
            "platform_fee_recorded_at",
            "giveaway_prize_cents",
            "page_layout",
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


def _mask_email(e: str | None) -> str | None:
    """Mask email for public display (e.g. j***n@example.com)."""
    if not e:
        return None
    local, _, domain = e.partition("@")
    if not domain:
        return e
    if len(local) <= 2:
        masked = local[:1] + "***"
    else:
        masked = local[0] + "***" + local[-1]
    return masked + "@" + domain


def get_latest_winner_public(campaign_id: str) -> dict[str, Any] | None:
    """
    Fetch the most recent giveaway winner for public display.
    Returns { donor, amount_cents, created_at } or None.
    """
    sql = """
      SELECT gl.winner_donation_id, gl.created_at, d.amount_cents, d.donor_email
      FROM giveaway_logs gl
      LEFT JOIN donations d ON d.id = gl.winner_donation_id
      WHERE gl.campaign_id = %s AND gl.winner_donation_id IS NOT NULL
      ORDER BY gl.created_at DESC
      LIMIT 1
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        if not row:
            return None
        winner_donation_id, created_at, amount_cents, donor_email = row
        donor = _mask_email(donor_email) if donor_email else "Anonymous"
        return {
            "donor": donor,
            "amount_cents": int(amount_cents or 0),
            "created_at": (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            ),
        }


def list_giveaway_logs(campaign_id: str, limit: int = 20) -> list[dict]:
    sql = """
      SELECT gl.campaign_id, gl.winner_donation_id, gl.mode, gl.population_count, gl.created_at,
             d.donor_email
      FROM giveaway_logs gl
      LEFT JOIN donations d ON d.id = gl.winner_donation_id
      WHERE gl.campaign_id = %s
      ORDER BY gl.created_at DESC
      LIMIT %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, limit))
        rows = cur.fetchall()
        result = []
        for r in rows:
            donor_email = r[5] if len(r) > 5 else None
            created_at = r[4]
            result.append(
                {
                    "campaign_id": r[0],
                    "winner_donation_id": r[1],
                    "mode": r[2],
                    "population_count": r[3],
                    "created_at": (
                        created_at.isoformat()
                        if hasattr(created_at, "isoformat")
                        else str(created_at)
                    ),
                    "winner_donor": (
                        _mask_email(donor_email) if donor_email else "Anonymous"
                    ),
                }
            )
        return result
