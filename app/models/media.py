from typing import Any
from app.utils.db import get_db_connection


def create_campaign_media(
    *,
    org_id: str,
    campaign_id: str,
    type: str,
    s3_key: str,
    content_type: str | None,
    size_bytes: int | None,
    url: str | None,
    description: str | None,
    sort: int | None = 0,
) -> dict[str, Any]:
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
