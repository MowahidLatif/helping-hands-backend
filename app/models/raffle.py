from typing import Any, Dict, List, Optional
from app.utils.db import get_db_connection


def _row_to_dict(cur, row) -> Dict[str, Any]:
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


# ---------------------------------------------------------------------------
# Raffles
# ---------------------------------------------------------------------------

def create_raffle(
    campaign_id: str,
    prize_name: str,
    prize_description: Optional[str],
    prize_image_url: Optional[str],
    compliance_ack_at,
) -> Dict[str, Any]:
    sql = """
        INSERT INTO raffles
            (campaign_id, prize_name, prize_description, prize_image_url,
             status, compliance_ack_at)
        VALUES (%s, %s, %s, %s, 'active', %s)
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, prize_name, prize_description,
                          prize_image_url, compliance_ack_at))
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row)


def get_raffle_by_campaign(campaign_id: str) -> Optional[Dict[str, Any]]:
    sql = "SELECT * FROM raffles WHERE campaign_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_raffle_by_id(raffle_id: str) -> Optional[Dict[str, Any]]:
    sql = "SELECT * FROM raffles WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def update_raffle(raffle_id: str, **fields) -> Optional[Dict[str, Any]]:
    allowed = {
        "prize_name", "prize_description", "prize_image_url", "status",
        "winner_entry_id", "redraw_count", "max_redraws",
        "claim_deadline", "ended_at",
    }
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return get_raffle_by_id(raffle_id)
    clauses = ", ".join(f"{k} = %s" for k in sets)
    values = list(sets.values()) + [raffle_id]
    sql = f"UPDATE raffles SET {clauses} WHERE id = %s RETURNING *"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, values)
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row) if row else None


def get_pending_claim_raffles() -> List[Dict[str, Any]]:
    """Return raffles with status=winner_pending whose claim_deadline has passed."""
    sql = """
        SELECT * FROM raffles
        WHERE status = 'winner_pending'
          AND claim_deadline < now()
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]


# ---------------------------------------------------------------------------
# Raffle Entries
# ---------------------------------------------------------------------------

def upsert_raffle_entry(
    raffle_id: str,
    donor_email: str,
    donor_first_name: Optional[str],
    donor_last_name: Optional[str],
    display_consent: bool,
    source: str,
    donation_id: Optional[str],
) -> Dict[str, Any]:
    sql = """
        INSERT INTO raffle_entries
            (raffle_id, donor_email, donor_first_name, donor_last_name,
             display_consent, source, donation_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raffle_id, donor_email)
        DO UPDATE SET
            display_consent = EXCLUDED.display_consent,
            donor_first_name = COALESCE(EXCLUDED.donor_first_name, raffle_entries.donor_first_name),
            donor_last_name  = COALESCE(EXCLUDED.donor_last_name,  raffle_entries.donor_last_name)
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id, donor_email, donor_first_name,
                          donor_last_name, display_consent, source, donation_id))
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row)


def get_raffle_entries(raffle_id: str) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM raffle_entries WHERE raffle_id = %s ORDER BY created_at ASC"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]


def get_entry_count(raffle_id: str) -> int:
    sql = "SELECT COUNT(*) FROM raffle_entries WHERE raffle_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        return cur.fetchone()[0]


def get_undrawn_entries(raffle_id: str) -> List[Dict[str, Any]]:
    """Return entries that have never been drawn (not in raffle_draw_log for this raffle)."""
    sql = """
        SELECT e.* FROM raffle_entries e
        WHERE e.raffle_id = %s
          AND e.id NOT IN (
              SELECT entry_id FROM raffle_draw_log WHERE raffle_id = %s
          )
        ORDER BY e.created_at ASC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id, raffle_id))
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]


def get_entry_by_id(entry_id: str) -> Optional[Dict[str, Any]]:
    sql = "SELECT * FROM raffle_entries WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (entry_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


# ---------------------------------------------------------------------------
# Raffle Draw Log
# ---------------------------------------------------------------------------

def create_draw_log(raffle_id: str, entry_id: str) -> Dict[str, Any]:
    sql = """
        INSERT INTO raffle_draw_log (raffle_id, entry_id, outcome)
        VALUES (%s, %s, 'notified')
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id, entry_id))
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row)


def update_draw_log(log_id: str, outcome: str, claimed_at=None) -> Optional[Dict[str, Any]]:
    sql = """
        UPDATE raffle_draw_log
        SET outcome = %s, claimed_at = %s
        WHERE id = %s
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (outcome, claimed_at, log_id))
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row) if row else None


def get_current_draw_log(raffle_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent draw log row for a raffle."""
    sql = """
        SELECT * FROM raffle_draw_log
        WHERE raffle_id = %s
        ORDER BY drawn_at DESC
        LIMIT 1
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def get_draw_log_for_raffle(raffle_id: str) -> List[Dict[str, Any]]:
    sql = """
        SELECT * FROM raffle_draw_log
        WHERE raffle_id = %s
        ORDER BY drawn_at ASC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        rows = cur.fetchall()
        return [_row_to_dict(cur, r) for r in rows]
