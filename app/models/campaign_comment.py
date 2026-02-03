from typing import Any, List, Dict, Optional
from app.utils.db import get_db_connection


def create_comment(campaign_id: str, user_id: str, body: str) -> dict[str, Any]:
    sql = """
    INSERT INTO campaign_comments (campaign_id, user_id, body)
    VALUES (%s, %s, %s)
    RETURNING id, campaign_id, user_id, body, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, user_id, body))
        row = cur.fetchone()
        conn.commit()
        cols = ["id", "campaign_id", "user_id", "body", "created_at", "updated_at"]
        return dict(zip(cols, row))


def get_comment(comment_id: str) -> Optional[Dict[str, Any]]:
    sql = """
    SELECT c.id, c.campaign_id, c.user_id, c.body, c.created_at, c.updated_at,
           u.email, u.name
    FROM campaign_comments c
    JOIN users u ON u.id = c.user_id
    WHERE c.id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (comment_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "campaign_id": row[1],
            "user_id": row[2],
            "body": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "author_email": row[6],
            "author_name": row[7],
        }


def list_comments(
    campaign_id: str, limit: int = 50, after: Optional[str] = None
) -> List[Dict[str, Any]]:
    if after:
        sql = """
        SELECT c.id, c.campaign_id, c.user_id, c.body, c.created_at, c.updated_at,
               u.email, u.name
        FROM campaign_comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.campaign_id = %s AND c.created_at < (SELECT created_at FROM campaign_comments WHERE id = %s)
        ORDER BY c.created_at DESC
        LIMIT %s
        """
        params = (campaign_id, after, limit)
    else:
        sql = """
        SELECT c.id, c.campaign_id, c.user_id, c.body, c.created_at, c.updated_at,
               u.email, u.name
        FROM campaign_comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.campaign_id = %s
        ORDER BY c.created_at DESC
        LIMIT %s
        """
        params = (campaign_id, limit)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "campaign_id": r[1],
                "user_id": r[2],
                "body": r[3],
                "created_at": r[4],
                "updated_at": r[5],
                "author_email": r[6],
                "author_name": r[7],
            }
            for r in rows
        ]


def update_comment(
    comment_id: str, user_id: str, body: str
) -> Optional[Dict[str, Any]]:
    sql = """
    UPDATE campaign_comments
    SET body = %s, updated_at = now()
    WHERE id = %s AND user_id = %s
    RETURNING id, campaign_id, user_id, body, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (body, comment_id, user_id))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        cols = ["id", "campaign_id", "user_id", "body", "created_at", "updated_at"]
        return dict(zip(cols, row))


def delete_comment(comment_id: str, user_id: str) -> bool:
    sql = "DELETE FROM campaign_comments WHERE id = %s AND user_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (comment_id, user_id))
        conn.commit()
        return cur.rowcount > 0
