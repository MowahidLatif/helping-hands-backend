from typing import Any
from datetime import datetime
from app.utils.db import get_db_connection
from app.utils.slug import slugify as _slugify
import secrets

_ORG_SELECT_COLS = """
  id, name, subdomain, stripe_connect_account_id, payout_account_ready,
  payout_onboarding_status, payouts_enabled, created_at, updated_at, tier,
  stripe_customer_id, stripe_subscription_id, subscription_status,
  subscription_current_period_end, pending_tier,
  subscription_cancel_at_period_end, subscription_cancel_at,
  billing_interval, trial_ends_at, payment_grace_ends_at
"""


def _row_to_org(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0],
        "name": row[1],
        "subdomain": row[2],
        "stripe_connect_account_id": row[3],
        "payout_account_ready": bool(row[4]),
        "payout_onboarding_status": row[5],
        "payouts_enabled": bool(row[6]),
        "created_at": row[7],
        "updated_at": row[8],
        "tier": int(row[9]) if row[9] is not None else 1,
        "stripe_customer_id": row[10],
        "stripe_subscription_id": row[11],
        "subscription_status": row[12] or "legacy",
        "subscription_current_period_end": row[13],
        "pending_tier": int(row[14]) if row[14] is not None else None,
        "subscription_cancel_at_period_end": bool(row[15]) if row[15] is not None else False,
        "subscription_cancel_at": row[16],
        "billing_interval": row[17],
        "trial_ends_at": row[18],
        "payment_grace_ends_at": row[19],
    }


def create_organization(
    name: str,
    subdomain: str | None = None,
    tier: int = 1,
    *,
    pending_tier: int | None = None,
    subscription_status: str = "none",
):
    sub = _slugify(subdomain or name) or f"org-{secrets.token_hex(3)}"
    tier = int(tier) if tier in (1, 2, 3) else 1
    pending = int(pending_tier) if pending_tier in (1, 2, 3) else None
    status = (subscription_status or "none").strip().lower()

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO organizations (
              name, subdomain, tier, pending_tier, subscription_status
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id, name, subdomain, tier, pending_tier, subscription_status
            """,
            (name, sub, tier, pending, status),
        )
        row = cur.fetchone()
        conn.commit()

    return {
        "id": row[0],
        "name": row[1],
        "subdomain": row[2],
        "tier": row[3],
        "pending_tier": row[4],
        "subscription_status": row[5],
    }


def get_organization(org_id: str) -> dict[str, Any] | None:
    sql = f"SELECT {_ORG_SELECT_COLS} FROM organizations WHERE id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_org(row)


def get_organization_by_stripe_customer(customer_id: str) -> dict[str, Any] | None:
    sql = f"SELECT {_ORG_SELECT_COLS} FROM organizations WHERE stripe_customer_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (customer_id,))
        row = cur.fetchone()
        return _row_to_org(row) if row else None


def get_organization_by_connect_account(account_id: str) -> dict[str, Any] | None:
    sql = f"SELECT {_ORG_SELECT_COLS} FROM organizations WHERE stripe_connect_account_id = %s"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (account_id,))
        row = cur.fetchone()
        return _row_to_org(row) if row else None


def update_org_tier(org_id: str, tier: int) -> dict[str, Any] | None:
    tier = int(tier) if tier in (1, 2, 3) else 1
    sql = "UPDATE organizations SET tier = %s, updated_at = now() WHERE id = %s RETURNING id, tier"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (tier, org_id))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "tier": row[1]} if row else None


def update_org_billing(
    org_id: str,
    *,
    stripe_customer_id: str | None = None,
    stripe_connect_account_id: str | None = None,
    pending_tier: int | None = None,
    billing_interval: str | None = None,
) -> dict[str, Any] | None:
    sets: list[str] = []
    params: list[Any] = []
    if stripe_customer_id is not None:
        sets.append("stripe_customer_id = %s")
        params.append(stripe_customer_id)
    if stripe_connect_account_id is not None:
        sets.append("stripe_connect_account_id = %s")
        params.append(stripe_connect_account_id)
    if pending_tier is not None:
        sets.append("pending_tier = %s")
        params.append(int(pending_tier) if pending_tier in (1, 2, 3) else None)
    if billing_interval is not None:
        sets.append("billing_interval = %s")
        iv = (billing_interval or "").strip().lower()
        params.append(iv if iv in ("monthly", "annual") else None)
    if not sets:
        return get_organization(org_id)
    sets.append("updated_at = now()")
    sql = f"UPDATE organizations SET {', '.join(sets)} WHERE id = %s RETURNING id"
    params.append(org_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        conn.commit()
        return get_organization(str(row[0])) if row else None


def update_org_subscription(
    org_id: str,
    *,
    stripe_subscription_id: str | None = None,
    subscription_status: str | None = None,
    subscription_current_period_end: datetime | None = None,
    tier: int | None = None,
    pending_tier: int | None = ...,  # type: ignore[assignment]
    subscription_cancel_at_period_end: bool | None = None,
    subscription_cancel_at: datetime | None = ...,  # type: ignore[assignment]
    billing_interval: str | None = None,
    trial_ends_at: datetime | None = ...,  # type: ignore[assignment]
    payment_grace_ends_at: datetime | None = ...,  # type: ignore[assignment]
) -> dict[str, Any] | None:
    sets: list[str] = []
    params: list[Any] = []
    if stripe_subscription_id is not None:
        sets.append("stripe_subscription_id = %s")
        params.append(stripe_subscription_id)
    if subscription_status is not None:
        sets.append("subscription_status = %s")
        params.append(subscription_status)
    if subscription_current_period_end is not None:
        sets.append("subscription_current_period_end = %s")
        params.append(subscription_current_period_end)
    if tier is not None:
        sets.append("tier = %s")
        params.append(int(tier) if tier in (1, 2, 3) else 1)
    if pending_tier is not ...:
        sets.append("pending_tier = %s")
        params.append(int(pending_tier) if pending_tier in (1, 2, 3) else None)
    if subscription_cancel_at_period_end is not None:
        sets.append("subscription_cancel_at_period_end = %s")
        params.append(bool(subscription_cancel_at_period_end))
    if subscription_cancel_at is not ...:
        sets.append("subscription_cancel_at = %s")
        params.append(subscription_cancel_at)
    if billing_interval is not None:
        sets.append("billing_interval = %s")
        iv = (billing_interval or "").strip().lower()
        params.append(iv if iv in ("monthly", "annual") else None)
    if trial_ends_at is not ...:
        sets.append("trial_ends_at = %s")
        params.append(trial_ends_at)
    if payment_grace_ends_at is not ...:
        sets.append("payment_grace_ends_at = %s")
        params.append(payment_grace_ends_at)
    if not sets:
        return get_organization(org_id)
    sets.append("updated_at = now()")
    sql = f"UPDATE organizations SET {', '.join(sets)} WHERE id = %s RETURNING id"
    params.append(org_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        conn.commit()
        return get_organization(str(row[0])) if row else None


def list_user_organizations(user_id: str) -> list[dict[str, Any]]:
    sql = """
      SELECT o.id, o.name, ou.role
      FROM organizations o
      JOIN org_users ou ON ou.org_id = o.id
      WHERE ou.user_id = %s
      ORDER BY o.created_at ASC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        return [{"id": r[0], "name": r[1], "role": r[2]} for r in cur.fetchall()]


def update_organization_name(org_id: str, name: str) -> dict[str, Any] | None:
    sql = "UPDATE organizations SET name = %s, updated_at = now() WHERE id = %s RETURNING id, name"
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (name, org_id))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "name": row[1]} if row else None


def upsert_org_payout_account(
    *,
    org_id: str,
    stripe_connect_account_id: str | None,
    payout_account_ready: bool | None = None,
    payout_onboarding_status: str | None = None,
    payouts_enabled: bool | None = None,
) -> dict[str, Any] | None:
    sets: list[str] = []
    params: list[Any] = []
    if stripe_connect_account_id is not None:
        sets.append("stripe_connect_account_id = %s")
        params.append(stripe_connect_account_id)
    if payout_account_ready is not None:
        sets.append("payout_account_ready = %s")
        params.append(bool(payout_account_ready))
    if payout_onboarding_status is not None:
        sets.append("payout_onboarding_status = %s")
        params.append(payout_onboarding_status)
    if payouts_enabled is not None:
        sets.append("payouts_enabled = %s")
        params.append(bool(payouts_enabled))
    if not sets:
        return get_organization(org_id)
    sets.append("updated_at = now()")
    sql = f"UPDATE organizations SET {', '.join(sets)} WHERE id = %s RETURNING id"
    params.append(org_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        conn.commit()
        return get_organization(str(row[0])) if row else None


def delete_organization(org_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM organizations WHERE id = %s", (org_id,))
        conn.commit()
        return cur.rowcount > 0
