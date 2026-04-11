"""Campaign-specific tasks with multi-assignees and status."""

from typing import Any, List, Optional
from app.utils.db import get_db_connection


def _normalize_assignee_ids(
    assignee_user_ids: Optional[List[str]] = None,
    assignee_user_id: Optional[str] = None,
) -> Optional[List[str]]:
    source = assignee_user_ids
    if source is None and assignee_user_id is not None:
        source = [assignee_user_id]
    if source is None:
        return None

    out: List[str] = []
    seen = set()
    for value in source:
        candidate = str(value or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out


def _set_task_assignees(cur, task_id: str, assignee_user_ids: List[str]) -> None:
    cur.execute("DELETE FROM campaign_task_assignees WHERE task_id = %s", (task_id,))
    for user_id in assignee_user_ids:
        cur.execute(
            """
            INSERT INTO campaign_task_assignees (task_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (task_id, user_id) DO NOTHING
            """,
            (task_id, user_id),
        )


def _serialize_task_row(row: tuple[Any, ...], campaign_title: Optional[str] = None) -> dict:
    raw_assignees = row[8] if row[8] is not None else []
    assignees: List[dict[str, Any]] = [
        {
            "user_id": str(a.get("user_id")) if a.get("user_id") else "",
            "name": a.get("name"),
            "email": a.get("email"),
        }
        for a in raw_assignees
        if a and a.get("user_id")
    ]
    primary = assignees[0] if assignees else None
    payload = {
        "id": str(row[0]),
        "campaign_id": str(row[1]),
        "title": row[2],
        "description": row[3],
        "status_id": str(row[4]) if row[4] else None,
        "created_at": row[5].isoformat() if row[5] else None,
        "updated_at": row[6].isoformat() if row[6] else None,
        "status_name": row[7],
        "assignees": assignees,
        # Backward compatibility for existing frontend fields.
        "assignee_user_id": primary["user_id"] if primary else None,
        "assignee_name": primary["name"] if primary else None,
        "assignee_email": primary["email"] if primary else None,
    }
    if campaign_title is not None:
        payload["campaign_title"] = campaign_title
    return payload


def list_campaign_tasks(campaign_id: str) -> List[dict[str, Any]]:
    sql = """
    SELECT
      t.id,
      t.campaign_id,
      t.title,
      t.description,
      t.status_id,
      t.created_at,
      t.updated_at,
      s.name AS status_name,
      COALESCE(
        json_agg(
          DISTINCT jsonb_build_object(
            'user_id', u.id::text,
            'name', u.name,
            'email', u.email
          )
        ) FILTER (WHERE u.id IS NOT NULL),
        '[]'::json
      ) AS assignees
    FROM campaign_tasks t
    LEFT JOIN task_statuses s ON s.id = t.status_id
    LEFT JOIN campaign_task_assignees cta ON cta.task_id = t.id
    LEFT JOIN users u ON u.id = cta.user_id
    WHERE t.campaign_id = %s
    GROUP BY t.id, s.name
    ORDER BY t.created_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        return [_serialize_task_row(r) for r in cur.fetchall()]


def list_org_campaign_tasks(
    org_id: str, campaign_id: Optional[str] = None
) -> List[dict[str, Any]]:
    sql = """
    SELECT
      t.id,
      t.campaign_id,
      t.title,
      t.description,
      t.status_id,
      t.created_at,
      t.updated_at,
      s.name AS status_name,
      COALESCE(
        json_agg(
          DISTINCT jsonb_build_object(
            'user_id', u.id::text,
            'name', u.name,
            'email', u.email
          )
        ) FILTER (WHERE u.id IS NOT NULL),
        '[]'::json
      ) AS assignees,
      c.title AS campaign_title
    FROM campaign_tasks t
    JOIN campaigns c ON c.id = t.campaign_id
    LEFT JOIN task_statuses s ON s.id = t.status_id
    LEFT JOIN campaign_task_assignees cta ON cta.task_id = t.id
    LEFT JOIN users u ON u.id = cta.user_id
    WHERE c.org_id = %s
    """
    params: list[Any] = [org_id]
    if campaign_id:
        sql += " AND t.campaign_id = %s"
        params.append(campaign_id)
    sql += " GROUP BY t.id, s.name, c.title ORDER BY t.created_at DESC"

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [_serialize_task_row(r, campaign_title=r[9]) for r in cur.fetchall()]


def get_campaign_task(task_id: str, campaign_id: str) -> Optional[dict[str, Any]]:
    sql = """
    SELECT
      t.id,
      t.campaign_id,
      t.title,
      t.description,
      t.status_id,
      t.created_at,
      t.updated_at,
      s.name AS status_name,
      COALESCE(
        json_agg(
          DISTINCT jsonb_build_object(
            'user_id', u.id::text,
            'name', u.name,
            'email', u.email
          )
        ) FILTER (WHERE u.id IS NOT NULL),
        '[]'::json
      ) AS assignees
    FROM campaign_tasks t
    LEFT JOIN task_statuses s ON s.id = t.status_id
    LEFT JOIN campaign_task_assignees cta ON cta.task_id = t.id
    LEFT JOIN users u ON u.id = cta.user_id
    WHERE t.id = %s AND t.campaign_id = %s
    GROUP BY t.id, s.name
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (task_id, campaign_id))
        row = cur.fetchone()
        if not row:
            return None
        return _serialize_task_row(row)


def create_campaign_task(
    campaign_id: str,
    title: str,
    description: Optional[str] = None,
    assignee_user_ids: Optional[List[str]] = None,
    assignee_user_id: Optional[str] = None,
    status_id: Optional[str] = None,
) -> dict[str, Any]:
    normalized_ids = _normalize_assignee_ids(assignee_user_ids, assignee_user_id) or []
    sql = """
    INSERT INTO campaign_tasks (campaign_id, title, description, status_id)
    VALUES (%s, %s, %s, %s)
    RETURNING id
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                campaign_id,
                (title or "").strip(),
                (description or "").strip() or None,
                status_id or None,
            ),
        )
        task_id = str(cur.fetchone()[0])
        _set_task_assignees(cur, task_id, normalized_ids)
        conn.commit()
        return get_campaign_task(task_id, campaign_id) or {}


def update_campaign_task(
    task_id: str,
    campaign_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    assignee_user_ids: Optional[List[str]] = None,
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
    if status_id is not None:
        updates.append("status_id = %s")
        params.append(status_id or None)

    normalized_ids = _normalize_assignee_ids(assignee_user_ids, assignee_user_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        if updates:
            updates.append("updated_at = now()")
            params.extend([task_id, campaign_id])
            sql = f"""
            UPDATE campaign_tasks SET {", ".join(updates)}
            WHERE id = %s AND campaign_id = %s
            RETURNING id
            """
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return None
        else:
            cur.execute(
                "SELECT id FROM campaign_tasks WHERE id = %s AND campaign_id = %s",
                (task_id, campaign_id),
            )
            row = cur.fetchone()
            if not row:
                return None

        if normalized_ids is not None:
            _set_task_assignees(cur, task_id, normalized_ids)

        conn.commit()
        return get_campaign_task(task_id, campaign_id)


def delete_campaign_task(task_id: str, campaign_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM campaign_tasks WHERE id = %s AND campaign_id = %s",
            (task_id, campaign_id),
        )
        conn.commit()
        return cur.rowcount > 0
