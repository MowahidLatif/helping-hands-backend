from typing import Any

from app.utils.db import get_db_connection
from app.utils.prompt_sanitize import sanitize_asset_description


def count_media_by_type(campaign_id: str) -> dict[str, int]:
    """Counts campaign_media rows by type (for upload quotas)."""
    sql = """
    SELECT type, COUNT(*)::int
    FROM campaign_media
    WHERE campaign_id = %s
    GROUP BY type
    """
    out = {"image": 0, "video": 0, "doc": 0, "embed": 0}
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        for row in cur.fetchall():
            t, c = row[0], row[1]
            if t in out:
                out[str(t)] = int(c)
    return out


def create_campaign_media(
    *,
    org_id: str,
    campaign_id: str,
    type: str,
    s3_key: str | None = None,
    content_type: str | None = None,
    size_bytes: int | None = None,
    url: str | None = None,
    description: str | None = None,
    sort: int | None = 0,
) -> dict[str, Any]:
    if description is not None:
        cleaned = sanitize_asset_description(description, max_len=500)
        description = cleaned if cleaned else None
    sql = """
    INSERT INTO campaign_media (org_id, campaign_id, type, s3_key, content_type, size_bytes, url, description, sort)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,0))
    RETURNING id, org_id, campaign_id, type, s3_key, content_type, size_bytes, url, description, sort, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                org_id,
                campaign_id,
                type,
                s3_key,
                content_type,
                size_bytes,
                url,
                description,
                sort,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "type",
            "s3_key",
            "content_type",
            "size_bytes",
            "url",
            "description",
            "sort",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def list_media_for_campaign(campaign_id: str) -> list[dict[str, Any]]:
    sql = """
    SELECT id, org_id, campaign_id, type, s3_key, content_type, size_bytes, url, description, sort, created_at, updated_at
    FROM campaign_media
    WHERE campaign_id = %s
    ORDER BY sort, created_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        rows = cur.fetchall()
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "type",
            "s3_key",
            "content_type",
            "size_bytes",
            "url",
            "description",
            "sort",
            "created_at",
            "updated_at",
        ]
        return [dict(zip(cols, r)) for r in rows]


def get_media_item(media_id: str) -> dict | None:
    sql = """
        SELECT id, org_id, campaign_id, type, s3_key, url
        FROM campaign_media
        WHERE id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (media_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(zip(["id", "org_id", "campaign_id", "type", "s3_key", "url"], row))


def delete_media_item(media_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM campaign_media WHERE id = %s RETURNING id",
            (media_id,),
        )
        row = cur.fetchone()
        conn.commit()
        return row is not None


def insert_media(campaign_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO media (campaign_id, type, url, title, description)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """,
        (
            campaign_id,
            data["type"],
            data["url"],
            data.get("title"),
            data.get("description"),
        ),
    )
    media = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return media


def select_media_by_campaign(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM media
        WHERE campaign_id = %s
        ORDER BY uploaded_at DESC;
    """,
        (campaign_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
