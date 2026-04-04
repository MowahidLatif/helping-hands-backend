from typing import Any
from app.utils.db import get_db_connection
from app.utils.slug import slugify as _slugify
import secrets


def create_organization(name: str, subdomain: str | None = None):
    sub = _slugify(subdomain or name) or f"org-{secrets.token_hex(3)}"

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO organizations (name, subdomain) VALUES (%s, %s) "
            "RETURNING id, name, subdomain",
            (name, sub),
        )
        row = cur.fetchone()
        conn.commit()

    return {"id": row[0], "name": row[1], "subdomain": row[2]}


def get_organization(org_id: str) -> dict[str, Any] | None:
    sql = """
      SELECT id, name, subdomain, stripe_connect_account_id, payout_account_ready,
             payout_onboarding_status, payouts_enabled, created_at, updated_at
      FROM organizations
      WHERE id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        row = cur.fetchone()
        if not row:
            return None
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
        }


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
    sql = f"""
      UPDATE organizations
      SET {", ".join(sets)}
      WHERE id = %s
      RETURNING id, name, subdomain, stripe_connect_account_id, payout_account_ready,
                payout_onboarding_status, payouts_enabled, created_at, updated_at
    """
    params.append(org_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return None
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
        }


def delete_organization(org_id: str) -> bool:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM organizations WHERE id = %s", (org_id,))
        conn.commit()
        return cur.rowcount > 0
