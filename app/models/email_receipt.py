from typing import Any, List, Dict, Optional
from app.utils.db import get_db_connection


def list_receipts_for_campaign(
    campaign_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    sql = """
      SELECT er.id, er.donation_id, er.to_email, er.subject, er.sent_at, er.created_at
      FROM email_receipts er
      JOIN donations d ON d.id = er.donation_id
      WHERE d.campaign_id = %s
      ORDER BY er.created_at DESC
      LIMIT %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, limit))
        rows = cur.fetchall()
        cols = ["id", "donation_id", "to_email", "subject", "sent_at", "created_at"]
        return [dict(zip(cols, r)) for r in rows]


def get_receipt(receipt_id: str) -> Optional[Dict[str, Any]]:
    sql = """
      SELECT
        er.id,
        d.org_id,
        d.campaign_id,
        er.donation_id,
        er.to_email,
        er.subject,
        er.body_html,
        er.sent_at,
        er.created_at
      FROM email_receipts er
      JOIN donations d ON d.id = er.donation_id
      WHERE er.id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (receipt_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "donation_id",
            "to_email",
            "subject",
            "body_html",
            "sent_at",
            "created_at",
        ]
        return dict(zip(cols, row))


def resend_receipt(receipt_id: str) -> Optional[Dict[str, Any]]:
    """
    Resend by updating the existing row (keep one row per donation).
    - Refresh sent_at.
    - Ensure body_text is non-NULL (derive from HTML if needed, then fallback).
    - Ensure body_html has a minimal fallback for preview/sanity.
    """
    sql = """
      WITH upd AS (
        UPDATE email_receipts er
        SET
          body_text = COALESCE(
            NULLIF(er.body_text, ''),
            NULLIF(regexp_replace(COALESCE(er.body_html, ''), E'<[^>]+>', '', 'g'), ''),
            'Thank you for your donation.'
          ),
          body_html = COALESCE(er.body_html, '<p>No content</p>'),
          sent_at   = now(),
          updated_at = now()
        WHERE er.id = %s
        RETURNING er.id, er.donation_id, er.to_email, er.subject, er.sent_at, er.created_at
      )
      SELECT * FROM upd
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (receipt_id,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        cols = ["id", "donation_id", "to_email", "subject", "sent_at", "created_at"]
        return dict(zip(cols, row))
