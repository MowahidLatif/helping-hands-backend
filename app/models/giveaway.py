from typing import List, Dict, Optional
from app.utils.db import get_db_connection


def get_campaign_org(campaign_id: str) -> Optional[str]:
    sql = "SELECT org_id FROM campaigns WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        return row[0] if row else None


def list_paid_donations(campaign_id: str, min_amount_cents: int = 0) -> List[Dict]:
    sql = """
      SELECT id, donor_email, amount_cents, created_at
      FROM donations
      WHERE campaign_id = %s
        AND status = 'succeeded'
        AND amount_cents >= %s
      ORDER BY created_at ASC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, min_amount_cents))
        rows = cur.fetchall()
        return [
            {"id": r[0], "donor_email": r[1], "amount_cents": r[2], "created_at": r[3]}
            for r in rows
        ]
