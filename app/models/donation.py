from typing import Any
from typing import List, Dict
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


# def list_succeeded_for_campaign(
#     campaign_id: str, min_amount_cents: int = 0
# ) -> list[dict[str, Any]]:
#     """
#     Return all succeeded donations for a campaign, optionally filtered by a minimum amount.
#     Ordered by created_at ascending (stable order for draws).
#     """
#     sql = """
#       SELECT id, donor_email, amount_cents, currency, created_at
#       FROM donations
#       WHERE campaign_id = %s
#         AND status = 'succeeded'
#         AND amount_cents >= %s
#       ORDER BY created_at ASC
#     """
#     with get_db_connection() as conn, conn.cursor() as cur:
#         cur.execute(sql, (campaign_id, min_amount_cents))
#         rows = cur.fetchall()
#         cols = ["id", "donor_email", "amount_cents", "currency", "created_at"]
#         return [dict(zip(cols, r)) for r in rows]


def list_succeeded_for_campaign(
    campaign_id: str,
    *,
    mode: str = "per_donation",
    min_amount_cents: int = 0,
) -> List[Dict[str, Any]]:
    """
    mode="per_donation": one entry per succeeded donation >= threshold
    mode="per_donor": one entry per donor whose SUM(amount_cents) meets threshold
    """
    if min_amount_cents is None:
        min_amount_cents = 0
    min_amount_cents = int(min_amount_cents)

    with get_db_connection() as conn, conn.cursor() as cur:
        if mode == "per_donor":
            sql = """
            SELECT
              (array_agg(id ORDER BY created_at ASC))[1] AS donation_id,
              LOWER(donor_email) AS donor_email,
              SUM(amount_cents)::int AS total_cents
            FROM donations
            WHERE campaign_id = %s
              AND status = 'succeeded'
              AND donor_email IS NOT NULL
            GROUP BY LOWER(donor_email)
            HAVING SUM(amount_cents) >= %s
            ORDER BY donor_email
            """
            cur.execute(sql, (campaign_id, min_amount_cents))
            rows = cur.fetchall()
            return [
                {
                    "donation_id": r[0],
                    "donor_email": r[1],
                    "amount_cents": r[2],
                }
                for r in rows
            ]
        else:
            sql = """
            SELECT id, COALESCE(LOWER(donor_email), NULL) AS donor_email, amount_cents::int
            FROM donations
            WHERE campaign_id = %s
              AND status = 'succeeded'
              AND amount_cents >= %s
            ORDER BY created_at
            """
            cur.execute(sql, (campaign_id, min_amount_cents))
            rows = cur.fetchall()
            return [
                {
                    "donation_id": r[0],
                    "donor_email": r[1],
                    "amount_cents": r[2],
                }
                for r in rows
            ]


def recent_succeeded_for_campaign(campaign_id: str, limit: int = 10) -> list[dict]:
    sql = """
      SELECT id, donor_email, amount_cents, currency, created_at
      FROM donations
      WHERE campaign_id = %s AND status = 'succeeded'
      ORDER BY created_at DESC
      LIMIT %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id, limit))
        rows = cur.fetchall()
        out = []
        for r in rows:
            did, email, cents, cur_code, ts = r
            masked = None
            if email:
                local, _, dom = email.partition("@")
                masked = (
                    (
                        local[:1] + "***" + local[-1]
                        if len(local) > 2
                        else (local[:1] + "***")
                    )
                    + "@"
                    + dom
                )
            out.append(
                {
                    "id": did,
                    "donor": masked,
                    "amount_cents": int(cents),
                    "amount": round(int(cents) / 100.0, 2),
                    "currency": cur_code or "usd",
                    "created_at": ts.isoformat() if ts else None,
                }
            )
        return out
