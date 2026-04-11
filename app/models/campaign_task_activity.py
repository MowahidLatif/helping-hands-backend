"""Task comments/activity, checklist, reactions, and notification intents."""

from typing import Any, Dict, List, Optional
from app.utils.db import get_db_connection


def create_task_comment(
    task_id: str,
    campaign_id: str,
    org_id: str,
    author_user_id: Optional[str],
    comment_type: str,
    body: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    mention_user_ids: Optional[List[str]] = None,
) -> dict[str, Any]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_comments (
              task_id, campaign_id, org_id, author_user_id, comment_type, body, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                task_id,
                campaign_id,
                org_id,
                author_user_id,
                (comment_type or "").strip(),
                (body or "").strip() or None,
                __import__("json").dumps(metadata or {}),
            ),
        )
        comment_id = str(cur.fetchone()[0])
        for uid in mention_user_ids or []:
            cur.execute(
                """
                INSERT INTO task_comment_mentions (comment_id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (comment_id, user_id) DO NOTHING
                """,
                (comment_id, uid),
            )
        conn.commit()
    row = get_task_comment(comment_id)
    return row or {"id": comment_id}


def get_task_comment(comment_id: str) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              c.id,
              c.task_id,
              c.comment_type,
              c.body,
              c.metadata,
              c.created_at,
              c.author_user_id,
              u.name,
              u.email,
              COALESCE(
                json_agg(DISTINCT jsonb_build_object('user_id', mu.id::text, 'name', mu.name, 'email', mu.email))
                FILTER (WHERE mu.id IS NOT NULL),
                '[]'::json
              ) AS mentions,
              COALESCE(
                json_agg(DISTINCT jsonb_build_object('user_id', ru.id::text, 'reaction', r.reaction))
                FILTER (WHERE ru.id IS NOT NULL),
                '[]'::json
              ) AS reactions
            FROM task_comments c
            LEFT JOIN users u ON u.id = c.author_user_id
            LEFT JOIN task_comment_mentions m ON m.comment_id = c.id
            LEFT JOIN users mu ON mu.id = m.user_id
            LEFT JOIN task_comment_reactions r ON r.comment_id = c.id
            LEFT JOIN users ru ON ru.id = r.user_id
            WHERE c.id = %s
            GROUP BY c.id, u.name, u.email
            """,
            (comment_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "task_id": str(row[1]),
            "comment_type": row[2],
            "body": row[3],
            "metadata": row[4] or {},
            "created_at": row[5].isoformat() if row[5] else None,
            "author_user_id": str(row[6]) if row[6] else None,
            "author_name": row[7],
            "author_email": row[8],
            "mentions": row[9] or [],
            "reactions": row[10] or [],
        }


def list_task_comments(task_id: str) -> List[dict[str, Any]]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM task_comments
            WHERE task_id = %s
            ORDER BY created_at ASC
            """,
            (task_id,),
        )
        ids = [str(r[0]) for r in cur.fetchall()]
    return [row for cid in ids if (row := get_task_comment(cid))]


def add_comment_reaction(comment_id: str, user_id: str, reaction: str) -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_comment_reactions (comment_id, user_id, reaction)
            VALUES (%s, %s, %s)
            ON CONFLICT (comment_id, user_id, reaction) DO NOTHING
            """,
            (comment_id, user_id, reaction),
        )
        conn.commit()


def create_checklist_item(
    task_id: str, campaign_id: str, org_id: str, title: str, created_by_user_id: str
) -> dict[str, Any]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_checklist_items (
              task_id, campaign_id, org_id, title, created_by_user_id
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, title, is_checked, checked_by_user_id, created_at, updated_at
            """,
            (task_id, campaign_id, org_id, (title or "").strip(), created_by_user_id),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "id": str(row[0]),
            "task_id": task_id,
            "title": row[1],
            "is_checked": bool(row[2]),
            "checked_by_user_id": str(row[3]) if row[3] else None,
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
        }


def list_checklist_items(task_id: str) -> List[dict[str, Any]]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, is_checked, checked_by_user_id, created_at, updated_at
            FROM task_checklist_items
            WHERE task_id = %s
            ORDER BY created_at ASC
            """,
            (task_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "task_id": task_id,
                "title": r[1],
                "is_checked": bool(r[2]),
                "checked_by_user_id": str(r[3]) if r[3] else None,
                "created_at": r[4].isoformat() if r[4] else None,
                "updated_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]


def update_checklist_item(
    checklist_id: str, task_id: str, is_checked: bool, checked_by_user_id: Optional[str]
) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE task_checklist_items
            SET is_checked = %s,
                checked_by_user_id = %s,
                updated_at = now()
            WHERE id = %s AND task_id = %s
            RETURNING id, title, is_checked, checked_by_user_id, created_at, updated_at
            """,
            (bool(is_checked), checked_by_user_id, checklist_id, task_id),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "task_id": task_id,
            "title": row[1],
            "is_checked": bool(row[2]),
            "checked_by_user_id": str(row[3]) if row[3] else None,
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
        }


def create_time_entry(
    task_id: str,
    campaign_id: str,
    org_id: str,
    user_id: str,
    hours: float,
    note: Optional[str] = None,
) -> dict[str, Any]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO task_time_entries (task_id, campaign_id, org_id, user_id, hours, note)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (task_id, campaign_id, org_id, user_id, float(hours), (note or "").strip() or None),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "id": str(row[0]),
            "task_id": task_id,
            "user_id": user_id,
            "hours": float(hours),
            "note": (note or "").strip() or None,
            "created_at": row[1].isoformat() if row[1] else None,
        }


def create_notification_intents(
    task_id: str,
    org_id: str,
    recipient_user_ids: List[str],
    event_type: str,
    comment_id: Optional[str] = None,
) -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        for recipient_user_id in recipient_user_ids:
            cur.execute(
                """
                INSERT INTO task_notification_intents (
                  task_id, comment_id, org_id, recipient_user_id, event_type, channel
                )
                VALUES (%s, %s, %s, %s, %s, 'email')
                """,
                (task_id, comment_id, org_id, recipient_user_id, event_type),
            )
        conn.commit()
