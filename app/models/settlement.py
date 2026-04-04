from __future__ import annotations

from typing import Any
from psycopg2.extras import Json

from app.utils.db import get_db_connection


def upsert_campaign_settlement(
    *,
    campaign_id: str,
    org_id: str,
    fee_option: str,
    fee_policy_version: str,
    gross_raised_cents: int,
    stripe_fee_cents: int,
    platform_fee_cents: int,
    donor_covered_fee_cents: int,
    platform_absorbed_fee_cents: int,
    refunded_cents: int,
    disputed_cents: int,
    net_payout_cents: int,
    status: str = "pending",
) -> dict[str, Any]:
    sql = """
      INSERT INTO campaign_settlements (
        campaign_id, org_id, fee_option, fee_policy_version, gross_raised_cents,
        stripe_fee_cents, platform_fee_cents, donor_covered_fee_cents,
        platform_absorbed_fee_cents, refunded_cents, disputed_cents, net_payout_cents,
        status, settled_at
      )
      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
      ON CONFLICT (campaign_id)
      DO UPDATE
      SET fee_option = EXCLUDED.fee_option,
          fee_policy_version = EXCLUDED.fee_policy_version,
          gross_raised_cents = EXCLUDED.gross_raised_cents,
          stripe_fee_cents = EXCLUDED.stripe_fee_cents,
          platform_fee_cents = EXCLUDED.platform_fee_cents,
          donor_covered_fee_cents = EXCLUDED.donor_covered_fee_cents,
          platform_absorbed_fee_cents = EXCLUDED.platform_absorbed_fee_cents,
          refunded_cents = EXCLUDED.refunded_cents,
          disputed_cents = EXCLUDED.disputed_cents,
          net_payout_cents = EXCLUDED.net_payout_cents,
          status = EXCLUDED.status,
          settled_at = now(),
          updated_at = now()
      RETURNING id, campaign_id, org_id, fee_option, fee_policy_version, gross_raised_cents,
                stripe_fee_cents, platform_fee_cents, donor_covered_fee_cents,
                platform_absorbed_fee_cents, refunded_cents, disputed_cents,
                net_payout_cents, status, payout_attempts, last_error, settled_at,
                created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                campaign_id,
                org_id,
                fee_option,
                fee_policy_version,
                int(gross_raised_cents),
                int(stripe_fee_cents),
                int(platform_fee_cents),
                int(donor_covered_fee_cents),
                int(platform_absorbed_fee_cents),
                int(refunded_cents),
                int(disputed_cents),
                int(net_payout_cents),
                status,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    cols = [
        "id",
        "campaign_id",
        "org_id",
        "fee_option",
        "fee_policy_version",
        "gross_raised_cents",
        "stripe_fee_cents",
        "platform_fee_cents",
        "donor_covered_fee_cents",
        "platform_absorbed_fee_cents",
        "refunded_cents",
        "disputed_cents",
        "net_payout_cents",
        "status",
        "payout_attempts",
        "last_error",
        "settled_at",
        "created_at",
        "updated_at",
    ]
    return dict(zip(cols, row))


def get_campaign_settlement(campaign_id: str) -> dict[str, Any] | None:
    sql = """
      SELECT id, campaign_id, org_id, fee_option, fee_policy_version, gross_raised_cents,
             stripe_fee_cents, platform_fee_cents, donor_covered_fee_cents,
             platform_absorbed_fee_cents, refunded_cents, disputed_cents,
             net_payout_cents, status, payout_attempts, last_error, settled_at,
             created_at, updated_at
      FROM campaign_settlements
      WHERE campaign_id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        row = cur.fetchone()
        if not row:
            return None
    cols = [
        "id",
        "campaign_id",
        "org_id",
        "fee_option",
        "fee_policy_version",
        "gross_raised_cents",
        "stripe_fee_cents",
        "platform_fee_cents",
        "donor_covered_fee_cents",
        "platform_absorbed_fee_cents",
        "refunded_cents",
        "disputed_cents",
        "net_payout_cents",
        "status",
        "payout_attempts",
        "last_error",
        "settled_at",
        "created_at",
        "updated_at",
    ]
    return dict(zip(cols, row))


def increment_settlement_attempt(
    settlement_id: str, *, status: str, last_error: str | None = None
) -> None:
    sql = """
      UPDATE campaign_settlements
      SET payout_attempts = payout_attempts + 1,
          status = %s,
          last_error = %s,
          updated_at = now()
      WHERE id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (status, last_error, settlement_id))
        conn.commit()


def set_settlement_status(
    settlement_id: str, status: str, last_error: str | None = None
) -> None:
    sql = """
      UPDATE campaign_settlements
      SET status = %s,
          last_error = %s,
          updated_at = now()
      WHERE id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (status, last_error, settlement_id))
        conn.commit()


def create_campaign_payout(
    *,
    settlement_id: str,
    campaign_id: str,
    org_id: str,
    amount_cents: int,
    currency: str,
    idempotency_key: str,
    stripe_transfer_id: str | None,
    stripe_payout_id: str | None,
    status: str,
    failure_reason: str | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sql = """
      INSERT INTO campaign_payouts (
        settlement_id, campaign_id, org_id, amount_cents, currency, idempotency_key,
        stripe_transfer_id, stripe_payout_id, status, failure_reason, raw
      )
      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
      RETURNING id, settlement_id, campaign_id, org_id, amount_cents, currency,
                idempotency_key, stripe_transfer_id, stripe_payout_id, status,
                failure_reason, raw, created_at, updated_at
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            (
                settlement_id,
                campaign_id,
                org_id,
                int(amount_cents),
                currency,
                idempotency_key,
                stripe_transfer_id,
                stripe_payout_id,
                status,
                failure_reason,
                Json(raw) if raw is not None else None,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    cols = [
        "id",
        "settlement_id",
        "campaign_id",
        "org_id",
        "amount_cents",
        "currency",
        "idempotency_key",
        "stripe_transfer_id",
        "stripe_payout_id",
        "status",
        "failure_reason",
        "raw",
        "created_at",
        "updated_at",
    ]
    return dict(zip(cols, row))


def list_campaign_payouts(campaign_id: str) -> list[dict[str, Any]]:
    sql = """
      SELECT id, settlement_id, campaign_id, org_id, amount_cents, currency,
             idempotency_key, stripe_transfer_id, stripe_payout_id, status,
             failure_reason, raw, created_at, updated_at
      FROM campaign_payouts
      WHERE campaign_id = %s
      ORDER BY created_at DESC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (campaign_id,))
        rows = cur.fetchall()
    cols = [
        "id",
        "settlement_id",
        "campaign_id",
        "org_id",
        "amount_cents",
        "currency",
        "idempotency_key",
        "stripe_transfer_id",
        "stripe_payout_id",
        "status",
        "failure_reason",
        "raw",
        "created_at",
        "updated_at",
    ]
    return [dict(zip(cols, row)) for row in rows]


def set_payout_status_by_transfer_id(
    transfer_id: str, *, status: str, raw: dict[str, Any] | None = None
) -> None:
    sql = """
      UPDATE campaign_payouts
      SET status = %s,
          raw = COALESCE(%s, raw),
          updated_at = now()
      WHERE stripe_transfer_id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (status, Json(raw) if raw is not None else None, transfer_id))
        conn.commit()


def set_payout_status_by_payout_id(
    payout_id: str, *, status: str, raw: dict[str, Any] | None = None
) -> None:
    sql = """
      UPDATE campaign_payouts
      SET status = %s,
          raw = COALESCE(%s, raw),
          updated_at = now()
      WHERE stripe_payout_id = %s
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (status, Json(raw) if raw is not None else None, payout_id))
        conn.commit()
