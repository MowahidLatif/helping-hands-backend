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


# def insert_giveaway_log(
#     org_id: str,
#     campaign_id: str,
#     winner_donation_id: str,
#     winner_email: Optional[str],
#     mode: str,
#     population_count: int,
#     population_hash: str,
#     created_by_user_id: str,
#     notes: Optional[str] = None,
# ) -> Dict:
#     sql = """
#       INSERT INTO giveaway_logs
#         (org_id, campaign_id, winner_donation_id, winner_email, mode,
#          population_count, population_hash, created_by_user_id, notes)
#       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
#       RETURNING id, created_at
#     """
#     with get_db_connection() as conn, conn.cursor() as cur:
#         cur.execute(
#             sql,
#             (
#                 org_id,
#                 campaign_id,
#                 winner_donation_id,
#                 winner_email,
#                 mode,
#                 population_count,
#                 population_hash,
#                 created_by_user_id,
#                 notes,
#             ),
#         )
#         row = cur.fetchone()
#         conn.commit()
#         return {"id": row[0], "created_at": row[1]}
