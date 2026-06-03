"""Track billing lifecycle emails sent per org (dedupe)."""

from __future__ import annotations

from app.utils.db import get_db_connection


def billing_email_already_sent(org_id: str, email_type: str) -> bool:
    sql = """
        SELECT 1 FROM billing_email_log
        WHERE org_id = %s AND email_type = %s
        LIMIT 1
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, email_type))
        return cur.fetchone() is not None


def record_billing_email_sent(org_id: str, email_type: str) -> None:
    sql = """
        INSERT INTO billing_email_log (org_id, email_type)
        VALUES (%s, %s)
        ON CONFLICT (org_id, email_type) DO NOTHING
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, email_type))
        conn.commit()
