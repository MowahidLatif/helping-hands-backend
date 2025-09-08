from typing import Any
from app.utils.db import get_db_connection


def create_donation(
    *,
    org_id: str,
    campaign_id: str,
    amount_cents: int,
    currency: str,
    donor_email: str | None,
) -> dict[str, Any]:
    sql = """
    INSERT INTO donations (org_id, campaign_id, amount_cents, currency, donor_email, status)
    VALUES (%s, %s, %s, %s, %s, 'initiated')
    RETURNING id, org_id, campaign_id, amount_cents, currency, donor_email, status, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id, campaign_id, amount_cents, currency, donor_email))
        row = cur.fetchone()
        conn.commit()
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "amount_cents",
            "currency",
            "donor_email",
            "status",
            "created_at",
            "updated_at",
        ]
        return dict(zip(cols, row))


def set_payment_intent(donation_id: str, pi_id: str) -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE donations SET stripe_payment_intent_id = %s, status = 'requires_payment', updated_at = now() WHERE id = %s",
            (pi_id, donation_id),
        )
        conn.commit()


def get_donation(donation_id: str) -> dict[str, Any] | None:
    sql = "SELECT id, org_id, campaign_id, amount_cents, currency, donor_email, status, stripe_payment_intent_id FROM donations WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (donation_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "amount_cents",
            "currency",
            "donor_email",
            "status",
            "stripe_payment_intent_id",
        ]
        return dict(zip(cols, row))


def insert_donation(data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO donations (campaign_id, donor_name, donor_email, amount, message)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *;
    """,
        (
            data["campaign_id"],
            data.get("donor_name"),
            data.get("donor_email"),
            data["amount"],
            data.get("message"),
        ),
    )
    donation = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return donation


def select_donations_by_campaign(campaign_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM donations
        WHERE campaign_id = %s
        ORDER BY donated_at DESC;
    """,
        (campaign_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_donation_by_pi(pi_id: str) -> dict[str, Any] | None:
    sql = """SELECT id, org_id, campaign_id, amount_cents, currency, donor_email, status, stripe_payment_intent_id
             FROM donations WHERE stripe_payment_intent_id = %s"""
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (pi_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [
            "id",
            "org_id",
            "campaign_id",
            "amount_cents",
            "currency",
            "donor_email",
            "status",
            "stripe_payment_intent_id",
        ]
        return dict(zip(cols, row))


def attach_pi_to_donation(donation_id: str, pi_id: str) -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE donations SET stripe_payment_intent_id=%s, updated_at=now() WHERE id=%s",
            (pi_id, donation_id),
        )
        conn.commit()


def set_status_by_id(donation_id: str, status: str) -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE donations SET status=%s, updated_at=now() WHERE id=%s",
            (status, donation_id),
        )
        conn.commit()


def set_status_by_pi(pi_id: str, status: str) -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE donations SET status=%s, updated_at=now() WHERE stripe_payment_intent_id=%s",
            (status, pi_id),
        )
        conn.commit()


def count_and_last_succeeded(campaign_id: str) -> tuple[int, str | None]:
    sql = """
      SELECT COUNT(*)::int AS cnt, MAX(created_at)::text AS last_dt
      FROM donations
      WHERE campaign_id = %s AND status = 'succeeded'
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        return (row[0], row[1])
