"""
Org tier definitions and feature-gate helpers.

Tier 1 (Starter)  — 3% platform fee
Tier 2 (Grow)     — 4% platform fee
Tier 3 (Scale)    — 5% platform fee
"""

from __future__ import annotations
from typing import Any
from app.utils.db import get_db_connection

CANCELLATION_FEE_PERCENT = 5.0

TIER_LIMITS: dict[int, dict[str, Any]] = {
    1: {
        "name": "Starter",
        "platform_fee_percent": 3.0,
        "max_active_campaigns": 2,
        "max_members": 1,
        "ai_gen_lifetime": 3,
        "ai_gen_per_month": None,
        "task_management": False,
        "task_management_full": False,
        "email_marketing": False,
        "giveaway": False,
        "iframe_embed": False,
        "campaign_updates": False,
        "basic_analytics": False,
        "advanced_analytics": False,
    },
    2: {
        "name": "Grow",
        "platform_fee_percent": 4.0,
        "max_active_campaigns": 5,
        "max_members": 5,
        "ai_gen_lifetime": None,
        "ai_gen_per_month": 10,
        "task_management": True,
        "task_management_full": False,
        "email_marketing": False,
        "giveaway": False,
        "iframe_embed": True,
        "campaign_updates": True,
        "basic_analytics": True,
        "advanced_analytics": False,
    },
    3: {
        "name": "Scale",
        "platform_fee_percent": 5.0,
        "max_active_campaigns": None,
        "max_members": None,
        "ai_gen_lifetime": None,
        "ai_gen_per_month": 30,
        "task_management": True,
        "task_management_full": True,
        "email_marketing": True,
        "giveaway": True,
        "iframe_embed": True,
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


def check_ai_generation_allowed(org_id: str) -> str | None:
    """Return an error message string if generation is not allowed, else None."""
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
    tier = get_org_tier(org_id)
    limits = TIER_LIMITS[tier]
    max_active = limits["max_active_campaigns"]
    if max_active is None:
        return None
    active = count_active_campaigns(org_id)
    if active >= max_active:
        return f"Active campaign limit reached ({max_active} on {limits['name']} plan). Upgrade or complete an existing campaign."
    return None


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
