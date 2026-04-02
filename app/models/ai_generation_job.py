from typing import Any
from app.utils.db import get_db_connection


def create_job(*, campaign_id: str, created_by_user_id: str) -> dict[str, Any]:
    sql = """
    INSERT INTO ai_generation_jobs (campaign_id, created_by_user_id, status, step, progress_percent)
    VALUES (%s, %s, 'pending', 'queued', 0)
    RETURNING id, campaign_id, created_by_user_id, status, step, progress_percent,
              error_message, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, created_by_user_id))
        row = cur.fetchone()
        conn.commit()
        cols = [
            "id",
            "campaign_id",
            "created_by_user_id",
            "status",
            "step",
            "progress_percent",
            "error_message",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def get_job(job_id: str, campaign_id: str | None = None) -> dict[str, Any] | None:
    sql = """
    SELECT id, campaign_id, created_by_user_id, status, step, progress_percent,
           error_message, created_at, updated_at
    FROM ai_generation_jobs WHERE id = %s
    """
    params: list[Any] = [job_id]
    if campaign_id:
        sql += " AND campaign_id = %s"
        params.append(campaign_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        if not row:
            return None
        cols = [
            "id",
            "campaign_id",
            "created_by_user_id",
            "status",
            "step",
            "progress_percent",
            "error_message",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def update_job(
    job_id: str,
    *,
    status: str | None = None,
    step: str | None = None,
    progress_percent: int | None = None,
    error_message: str | None = None,
) -> dict[str, Any] | None:
    sets, params = [], []
    if status is not None:
        sets.append("status = %s")
        params.append(status)
    if step is not None:
        sets.append("step = %s")
        params.append(step)
    if progress_percent is not None:
        sets.append("progress_percent = %s")
        params.append(progress_percent)
    if error_message is not None:
        sets.append("error_message = %s")
        params.append(error_message)
    if not sets:
        return get_job(job_id)
    sets.append("updated_at = now()")
    sql = f"""
    UPDATE ai_generation_jobs SET {', '.join(sets)} WHERE id = %s
    RETURNING id, campaign_id, created_by_user_id, status, step, progress_percent,
              error_message, created_at, updated_at
    """
    params.append(job_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        cols = [
            "id",
            "campaign_id",
            "created_by_user_id",
            "status",
            "step",
            "progress_percent",
            "error_message",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))
