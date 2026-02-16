"""Campaign-specific tasks with assignee and status."""

from typing import Any, List, Optional
from app.utils.db import get_db_connection


def list_campaign_tasks(campaign_id: str) -> List[dict[str, Any]]:
    sql = """
    SELECT t.id, t.campaign_id, t.title, t.description, t.assignee_user_id, t.status_id,
           t.created_at, t.updated_at,
           u.name AS assignee_name, u.email AS assignee_email,
           s.name AS status_name
    FROM campaign_tasks t
    LEFT JOIN users u ON u.id = t.assignee_user_id
    LEFT JOIN task_statuses s ON s.id = t.status_id
    WHERE t.campaign_id = %s
    ORDER BY t.created_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        return [
            {
                "id": str(r[0]),
                "campaign_id": str(r[1]),
                "title": r[2],
                "description": r[3],
                "assignee_user_id": str(r[4]) if r[4] else None,
                "status_id": str(r[5]) if r[5] else None,
                "created_at": r[6].isoformat() if r[6] else None,
                "updated_at": r[7].isoformat() if r[7] else None,
                "assignee_name": r[8],
                "assignee_email": r[9],
                "status_name": r[10],
            }
            for r in cur.fetchall()
        ]


def get_campaign_task(task_id: str, campaign_id: str) -> Optional[dict[str, Any]]:
    sql = """
    SELECT t.id, t.campaign_id, t.title, t.description, t.assignee_user_id, t.status_id,
           t.created_at, t.updated_at
    FROM campaign_tasks t
    WHERE t.id = %s AND t.campaign_id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (task_id, campaign_id))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "campaign_id": str(row[1]),
            "title": row[2],
            "description": row[3],
            "assignee_user_id": str(row[4]) if row[4] else None,
            "status_id": str(row[5]) if row[5] else None,
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
        }


def create_campaign_task(
    campaign_id: str,
    title: str,
    description: Optional[str] = None,
    assignee_user_id: Optional[str] = None,
    status_id: Optional[str] = None,
) -> dict[str, Any]:
    sql = """
    INSERT INTO campaign_tasks (campaign_id, title, description, assignee_user_id, status_id)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id, campaign_id, title, description, assignee_user_id, status_id, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                campaign_id,
                (title or "").strip(),
                (description or "").strip() or None,
                assignee_user_id or None,
                status_id or None,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "id": str(row[0]),
            "campaign_id": str(row[1]),
            "title": row[2],
            "description": row[3],
            "assignee_user_id": str(row[4]) if row[4] else None,
            "status_id": str(row[5]) if row[5] else None,
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
        }


def update_campaign_task(
    task_id: str,
    campaign_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    assignee_user_id: Optional[str] = None,
    status_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    updates = []
    params = []
    if title is not None:
        updates.append("title = %s")
        params.append((title or "").strip())
    if description is not None:
        updates.append("description = %s")
        params.append((description or "").strip() or None)
    if assignee_user_id is not None:
        updates.append("assignee_user_id = %s")
        params.append(assignee_user_id or None)
    if status_id is not None:
        updates.append("status_id = %s")
        params.append(status_id or None)
    if not updates:
        return get_campaign_task(task_id, campaign_id)
    updates.append("updated_at = now()")
    params.extend([task_id, campaign_id])
    sql = f"""
    UPDATE campaign_tasks SET {", ".join(updates)}
    WHERE id = %s AND campaign_id = %s
    RETURNING id, campaign_id, title, description, assignee_user_id, status_id, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "campaign_id": str(row[1]),
            "title": row[2],
            "description": row[3],
            "assignee_user_id": str(row[4]) if row[4] else None,
            "status_id": str(row[5]) if row[5] else None,
            "created_at": row[6].isoformat() if row[6] else None,
            "updated_at": row[7].isoformat() if row[7] else None,
        }


def delete_campaign_task(task_id: str, campaign_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM campaign_tasks WHERE id = %s AND campaign_id = %s",
            (task_id, campaign_id),
        )
        conn.commit()
        return cur.rowcount > 0
