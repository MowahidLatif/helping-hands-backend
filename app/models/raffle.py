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
    prize_value_cents: Optional[int] = None,
    min_entries: Optional[int] = None,
) -> Dict[str, Any]:
    sql = """
        INSERT INTO raffles
            (campaign_id, prize_name, prize_description, prize_image_url,
             status, compliance_ack_at, prize_value_cents, min_entries)
        VALUES (%s, %s, %s, %s, 'active', %s, %s, %s)
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, prize_name, prize_description,
                          prize_image_url, compliance_ack_at, prize_value_cents, min_entries))
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
        "claim_deadline", "ended_at", "prize_value_cents",
        "void_redraws", "claim_token_used_at", "min_entries",
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
# Org member email lookup (for self-dealing exclusion)
# ---------------------------------------------------------------------------

def get_org_member_emails(org_id: str) -> set:
    """Return lowercase emails of all current org team members."""
    sql = """
        SELECT LOWER(u.email)
        FROM org_users ou
        JOIN users u ON u.id = ou.user_id
        WHERE ou.org_id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        return {row[0] for row in cur.fetchall() if row[0]}


# ---------------------------------------------------------------------------
# Raffle Entries
# ---------------------------------------------------------------------------

def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone to E.164-ish: strip non-digits, prepend +1 for 10-digit NA numbers."""
    if not phone:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return phone.strip()[:20] or None


def upsert_raffle_entry(
    raffle_id: str,
    donor_email: str,
    donor_first_name: Optional[str],
    donor_last_name: Optional[str],
    display_consent: bool,
    source: str,
    donation_id: Optional[str],
    phone: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_phone = _normalize_phone(phone)
    sql = """
        INSERT INTO raffle_entries
            (raffle_id, donor_email, donor_first_name, donor_last_name,
             display_consent, source, donation_id, phone)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (raffle_id, donor_email)
        DO UPDATE SET
            display_consent = EXCLUDED.display_consent,
            donor_first_name = COALESCE(EXCLUDED.donor_first_name, raffle_entries.donor_first_name),
            donor_last_name  = COALESCE(EXCLUDED.donor_last_name,  raffle_entries.donor_last_name),
            phone = COALESCE(EXCLUDED.phone, raffle_entries.phone)
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id, donor_email, donor_first_name,
                          donor_last_name, display_consent, source, donation_id, normalized_phone))
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
    sql = "SELECT COUNT(*) FROM raffle_entries WHERE raffle_id = %s AND voided = false"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        return cur.fetchone()[0]


def get_undrawn_entries(raffle_id: str) -> List[Dict[str, Any]]:
    """Return valid (non-voided, non-deletion-requested) entries that have never been drawn."""
    sql = """
        SELECT e.* FROM raffle_entries e
        WHERE e.raffle_id = %s
          AND e.voided = false
          AND e.deletion_requested = false
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


def get_entry_by_donation(donation_id: str) -> Optional[Dict[str, Any]]:
    sql = "SELECT * FROM raffle_entries WHERE donation_id = %s LIMIT 1"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (donation_id,))
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None


def void_raffle_entry(entry_id: str, reason: str) -> Dict[str, Any]:
    sql = """
        UPDATE raffle_entries
        SET voided = true, voided_at = now(), void_reason = %s
        WHERE id = %s
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (reason, entry_id))
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row)


def get_valid_donation_count_for_entry(raffle_id: str, donor_email: str) -> int:
    """Count succeeded (non-refunded) donations from this email to the raffle's campaign."""
    sql = """
        SELECT COUNT(*)
        FROM donations d
        JOIN raffles r ON r.campaign_id = d.campaign_id
        WHERE r.id = %s
          AND LOWER(d.donor_email) = LOWER(%s)
          AND d.status = 'succeeded'
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id, donor_email))
        return cur.fetchone()[0]


def get_deletion_requested_entries(raffle_id: str) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM raffle_entries WHERE raffle_id = %s AND deletion_requested = true"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def hard_delete_entries_by_ids(entry_ids: List[str]) -> int:
    if not entry_ids:
        return 0
    placeholders = ", ".join("%s" for _ in entry_ids)
    sql = f"DELETE FROM raffle_entries WHERE id IN ({placeholders})"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, entry_ids)
        deleted = cur.rowcount
        conn.commit()
        return deleted


def get_all_entries_for_raffle(raffle_id: str) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM raffle_entries WHERE raffle_id = %s ORDER BY created_at ASC"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


def delete_all_entries_for_raffle(raffle_id: str) -> int:
    sql = "DELETE FROM raffle_entries WHERE raffle_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        deleted = cur.rowcount
        conn.commit()
        return deleted


def anonymize_draw_log(raffle_id: str) -> None:
    sql = "UPDATE raffle_draw_log SET entry_id = NULL WHERE raffle_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id,))
        conn.commit()


def mark_entry_deletion_requested(donor_email: str) -> int:
    """Set deletion_requested=true for all non-terminal entries by this email."""
    sql = """
        UPDATE raffle_entries
        SET deletion_requested = true
        WHERE LOWER(donor_email) = LOWER(%s)
          AND raffle_id IN (
              SELECT id FROM raffles WHERE status = 'active'
          )
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (donor_email,))
        updated = cur.rowcount
        conn.commit()
        return updated


def get_entries_in_terminal_raffles_by_email(donor_email: str) -> List[Dict[str, Any]]:
    """Return entries in already-terminal raffles for this email (safe to hard-delete)."""
    sql = """
        SELECT e.* FROM raffle_entries e
        JOIN raffles r ON r.id = e.raffle_id
        WHERE LOWER(e.donor_email) = LOWER(%s)
          AND r.status IN ('claimed', 'unclaimed', 'cancelled', 'cancelled_threshold')
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (donor_email,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Raffle Draw Log
# ---------------------------------------------------------------------------

def create_draw_log(
    raffle_id: str,
    entry_id: str,
    outcome: str = "notified",
    triggered_by: str = "scheduler",
) -> Dict[str, Any]:
    sql = """
        INSERT INTO raffle_draw_log (raffle_id, entry_id, outcome, triggered_by)
        VALUES (%s, %s, %s, %s)
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (raffle_id, entry_id, outcome, triggered_by))
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row)


def update_draw_log(log_id: str, outcome: str, claimed_at=None, expire_reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    sql = """
        UPDATE raffle_draw_log
        SET outcome = %s, claimed_at = %s, expire_reason = %s
        WHERE id = %s
        RETURNING *
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (outcome, claimed_at, expire_reason, log_id))
        row = cur.fetchone()
        conn.commit()
        return _row_to_dict(cur, row) if row else None


def get_draw_log_by_winner_email(email: str) -> List[Dict[str, Any]]:
    """Return draw log rows where the entry's email matches and outcome is 'notified'."""
    sql = """
        SELECT dl.* FROM raffle_draw_log dl
        JOIN raffle_entries e ON e.id = dl.entry_id
        WHERE LOWER(e.donor_email) = LOWER(%s)
          AND dl.outcome = 'notified'
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (email,))
        return [_row_to_dict(cur, r) for r in cur.fetchall()]


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
