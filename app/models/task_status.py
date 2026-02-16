"""Task statuses per org (e.g. Not started, In progress, Completed)."""

from typing import Any, List, Optional
from app.utils.db import get_db_connection


def list_task_statuses(org_id: str) -> List[dict[str, Any]]:
    sql = """
    SELECT id, org_id, name, sort_order, created_at
    FROM task_statuses WHERE org_id = %s ORDER BY sort_order, name
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        return [
            {
                "id": str(r[0]),
                "org_id": str(r[1]),
                "name": r[2],
                "sort_order": r[3],
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in cur.fetchall()
        ]


def create_task_status(org_id: str, name: str, sort_order: int = 0) -> dict[str, Any]:
    sql = """
    INSERT INTO task_statuses (org_id, name, sort_order)
    VALUES (%s, %s, %s)
    RETURNING id, org_id, name, sort_order, created_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, (name or "").strip(), sort_order))
        row = cur.fetchone()
        conn.commit()
        return {
            "id": str(row[0]),
            "org_id": str(row[1]),
            "name": row[2],
            "sort_order": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
        }


def get_task_status(status_id: str, org_id: str) -> Optional[dict[str, Any]]:
    sql = "SELECT id, org_id, name, sort_order FROM task_statuses WHERE id = %s AND org_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (status_id, org_id))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "org_id": str(row[1]),
            "name": row[2],
            "sort_order": row[3],
        }


def update_task_status(
    status_id: str,
    org_id: str,
    name: Optional[str] = None,
    sort_order: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    updates = []
    params = []
    if name is not None:
        updates.append("name = %s")
        params.append((name or "").strip())
    if sort_order is not None:
        updates.append("sort_order = %s")
        params.append(sort_order)
    if not updates:
        return get_task_status(status_id, org_id)
    params.extend([status_id, org_id])
    sql = f"""
    UPDATE task_statuses SET {", ".join(updates)}
    WHERE id = %s AND org_id = %s
    RETURNING id, org_id, name, sort_order
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "org_id": str(row[1]),
            "name": row[2],
            "sort_order": row[3],
        }


def delete_task_status(status_id: str, org_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM task_statuses WHERE id = %s AND org_id = %s",
            (status_id, org_id),
        )
        conn.commit()
        return cur.rowcount > 0


def status_in_use_by_tasks(status_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM campaign_tasks WHERE status_id = %s LIMIT 1", (status_id,)
        )
        return cur.fetchone() is not None
