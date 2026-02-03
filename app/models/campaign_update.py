from typing import Any, List, Dict, Optional
from app.utils.db import get_db_connection


def create_update(
    campaign_id: str, author_user_id: str, title: str, body: str
) -> dict[str, Any]:
    sql = """
    INSERT INTO campaign_updates (campaign_id, author_user_id, title, body)
    VALUES (%s, %s, %s, %s)
    RETURNING id, campaign_id, author_user_id, title, body, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, author_user_id, title, body))
        row = cur.fetchone()
        conn.commit()
        cols = [
            "id",
            "campaign_id",
            "author_user_id",
            "title",
            "body",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def get_update(update_id: str) -> Optional[Dict[str, Any]]:
    sql = """
    SELECT u.id, u.campaign_id, u.author_user_id, u.title, u.body,
           u.created_at, u.updated_at, usr.email, usr.name
    FROM campaign_updates u
    JOIN users usr ON usr.id = u.author_user_id
    WHERE u.id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (update_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "campaign_id": row[1],
            "author_user_id": row[2],
            "title": row[3],
            "body": row[4],
            "created_at": row[5],
            "updated_at": row[6],
            "author_email": row[7],
            "author_name": row[8],
        }


def list_updates(
    campaign_id: str, limit: int = 50, after: Optional[str] = None
) -> List[Dict[str, Any]]:
    if after:
        sql = """
        SELECT u.id, u.campaign_id, u.author_user_id, u.title, u.body,
               u.created_at, u.updated_at, usr.email, usr.name
        FROM campaign_updates u
        JOIN users usr ON usr.id = u.author_user_id
        WHERE u.campaign_id = %s AND u.created_at < (SELECT created_at FROM campaign_updates WHERE id = %s)
        ORDER BY u.created_at DESC
        LIMIT %s
        """
        params = (campaign_id, after, limit)
    else:
        sql = """
        SELECT u.id, u.campaign_id, u.author_user_id, u.title, u.body,
               u.created_at, u.updated_at, usr.email, usr.name
        FROM campaign_updates u
        JOIN users usr ON usr.id = u.author_user_id
        WHERE u.campaign_id = %s
        ORDER BY u.created_at DESC
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
                "author_user_id": r[2],
                "title": r[3],
                "body": r[4],
                "created_at": r[5],
                "updated_at": r[6],
                "author_email": r[7],
                "author_name": r[8],
            }
            for r in rows
        ]


def update_update(
    update_id: str, author_user_id: str, title: Optional[str], body: Optional[str]
) -> Optional[Dict[str, Any]]:
    updates, params = [], []
    if title is not None:
        updates.append("title = %s")
        params.append(title)
    if body is not None:
        updates.append("body = %s")
        params.append(body)
    if not updates:
        return get_update(update_id)
    updates.append("updated_at = now()")
    params.extend([update_id, author_user_id])
    sql = f"""
    UPDATE campaign_updates
    SET {", ".join(updates)}
    WHERE id = %s AND author_user_id = %s
    RETURNING id, campaign_id, author_user_id, title, body, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        cols = [
            "id",
            "campaign_id",
            "author_user_id",
            "title",
            "body",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def delete_update(update_id: str, author_user_id: str) -> bool:
    sql = "DELETE FROM campaign_updates WHERE id = %s AND author_user_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (update_id, author_user_id))
        conn.commit()
        return cur.rowcount > 0
