"""
Org tier definitions and feature-gate helpers.

Tier 1 (Starter)  — $10/month
Tier 2 (Grow)     — $40/month
Tier 3 (Scale)    — $100/month

Tiers gate features only. Donation payouts have no platform fee (v3 fee policy).
"""

from __future__ import annotations
from typing import Any
from app.utils.db import get_db_connection

TIER_LIMITS: dict[int, dict[str, Any]] = {
    1: {
        "name": "Starter",
        "monthly_price": 10,
        "max_active_campaigns": 1,
        "max_members": 1,
        "ai_gen_lifetime": None,
        "ai_gen_per_month": 3,
        "task_management": False,
        "task_management_full": False,
        "email_marketing": False,
        "giveaway": False,
        "raffle": False,
        "iframe_embed": False,
        "media_uploads": False,
        "campaign_updates": False,
        "basic_analytics": False,
        "advanced_analytics": False,
    },
    2: {
        "name": "Grow",
        "monthly_price": 40,
        "max_active_campaigns": 3,
        "max_members": 5,
        "ai_gen_lifetime": None,
        "ai_gen_per_month": 15,
        "task_management": True,
        "task_management_full": False,
        "email_marketing": False,
        "giveaway": False,
        "raffle": True,
        "iframe_embed": True,
        "media_uploads": True,
        "campaign_updates": True,
        "basic_analytics": True,
        "advanced_analytics": False,
    },
    3: {
        "name": "Scale",
        "monthly_price": 100,
        "max_active_campaigns": None,
        "max_members": None,
        "ai_gen_lifetime": None,
        "ai_gen_per_month": None,
        "task_management": True,
        "task_management_full": True,
        "email_marketing": True,
        "giveaway": True,
        "raffle": True,
        "iframe_embed": True,
        "media_uploads": True,
        "campaign_updates": True,
        "basic_analytics": True,
        "advanced_analytics": True,
    },
}

VALID_TIERS = frozenset(TIER_LIMITS.keys())


def get_org_tier(org_id: str) -> int:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT tier FROM organizations WHERE id = %s", (org_id,))
        row = cur.fetchone()
    return int(row[0]) if row else 1


def get_org_limits(org_id: str) -> dict[str, Any]:
    return TIER_LIMITS[get_org_tier(org_id)]


def count_active_campaigns(org_id: str) -> int:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM campaigns WHERE org_id = %s AND status = 'active'",
            (org_id,),
        )
        return int(cur.fetchone()[0])


def count_org_members(org_id: str) -> int:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM org_users WHERE org_id = %s",
            (org_id,),
        )
        return int(cur.fetchone()[0])


def count_ai_generations(org_id: str, month: bool = False) -> int:
    """Count AI site generation jobs for this org (all campaigns).

    If month=True, counts only jobs started in the current calendar month.
    """
    if month:
        sql = """
            SELECT COUNT(*) FROM ai_generation_jobs j
            JOIN campaigns c ON c.id = j.campaign_id
            WHERE c.org_id = %s
              AND j.status NOT IN ('failed')
              AND date_trunc('month', j.created_at) = date_trunc('month', now())
        """
    else:
        sql = """
            SELECT COUNT(*) FROM ai_generation_jobs j
            JOIN campaigns c ON c.id = j.campaign_id
            WHERE c.org_id = %s
              AND j.status NOT IN ('failed')
        """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        return int(cur.fetchone()[0])


def check_subscription_active(org_id: str) -> str | None:
    """Return error if org needs an active subscription to use paid features."""
    from app.models.org import get_organization
    from app.services.billing_service import org_has_active_billing, billing_required

    org = get_organization(org_id)
    if not org:
        return "Organization not found."
    if billing_required(org):
        return "An active subscription is required. Subscribe in Settings to continue."
    if not org_has_active_billing(org):
        return "An active subscription is required. Subscribe in Settings to continue."
    return None


def check_ai_generation_allowed(org_id: str) -> str | None:
    """Return an error message string if generation is not allowed, else None."""
    sub_err = check_subscription_active(org_id)
    if sub_err:
        return sub_err
    tier = get_org_tier(org_id)
    limits = TIER_LIMITS[tier]
    if limits["ai_gen_lifetime"] is not None:
        used = count_ai_generations(org_id, month=False)
        cap = limits["ai_gen_lifetime"]
        if used >= cap:
            return f"AI generation limit reached ({cap} lifetime on Starter plan). Upgrade to Grow or Scale for monthly generations."
    elif limits["ai_gen_per_month"] is not None:
        used = count_ai_generations(org_id, month=True)
        cap = limits["ai_gen_per_month"]
        if used >= cap:
            return f"Monthly AI generation limit reached ({cap}/month on {limits['name']} plan). Upgrade or wait until next month."
    return None


def check_campaign_creation_allowed(org_id: str) -> str | None:
    """Return an error message string if campaign creation is not allowed, else None."""
    sub_err = check_subscription_active(org_id)
    if sub_err:
        return sub_err
    tier = get_org_tier(org_id)
    limits = TIER_LIMITS[tier]
    max_active = limits["max_active_campaigns"]
    if max_active is None:
        return None
    active = count_active_campaigns(org_id)
    if active >= max_active:
        return f"Active campaign limit reached ({max_active} on {limits['name']} plan). Upgrade or complete an existing campaign."
    return None


def list_in_flight_campaigns(org_id: str) -> list[dict[str, Any]]:
    """Campaigns that are not completed, cancelled, or archived."""
    sql = """
        SELECT id, title, locked_tier, status
        FROM campaigns
        WHERE org_id = %s AND status NOT IN ('completed', 'cancelled', 'archived')
        ORDER BY created_at DESC
    """
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (org_id,))
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "locked_tier": int(r[2]) if r[2] is not None else 1,
            "locked_tier_name": TIER_LIMITS.get(int(r[2]) if r[2] else 1, {}).get("name", "Starter"),
            "status": r[3],
        }
        for r in rows
    ]


def check_tier_change_acknowledgment(org_id: str, acknowledged: bool) -> dict[str, Any] | None:
    """Return 409 payload when active campaigns exist and caller has not acknowledged."""
    if acknowledged:
        return None
    campaigns = list_in_flight_campaigns(org_id)
    if not campaigns:
        return None
    return {
        "requires_acknowledgment": True,
        "message": (
            "You have active campaigns on your account. "
            "Plan features and limits for these campaigns will update immediately. "
            "Acknowledge to proceed."
        ),
        "campaigns": campaigns,
    }


def check_member_add_allowed(org_id: str) -> str | None:
    """Return an error message string if adding a member is not allowed, else None."""
    tier = get_org_tier(org_id)
    limits = TIER_LIMITS[tier]
    max_members = limits["max_members"]
    if tier == 1:
        return "Team members are not available on the Starter plan. Upgrade to Grow to add team members."
    if max_members is None:
        return None
    current = count_org_members(org_id)
    if current >= max_members:
        return f"Member limit reached ({max_members} on {limits['name']} plan). Upgrade to Scale for unlimited members."
    return None
