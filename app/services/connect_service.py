"""Stripe Connect Express account provisioning and status sync."""

from __future__ import annotations

from typing import Any

import stripe

from app.models.org import get_organization, get_organization_by_connect_account, upsert_org_payout_account
from app.utils.stripe_config import (
    STRIPE_CONNECT_REFRESH_URL,
    STRIPE_CONNECT_RETURN_URL,
    STRIPE_SECRET_KEY,
)


def _stripe_configured() -> bool:
    return bool(STRIPE_SECRET_KEY)


def create_connect_onboarding_link(org_id: str) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    account_id = org.get("stripe_connect_account_id")
    if not account_id:
        return {"error": "stripe_connect_account_id not set"}
    if not _stripe_configured():
        return {"error": "Stripe is not configured"}
    if not STRIPE_CONNECT_REFRESH_URL or not STRIPE_CONNECT_RETURN_URL:
        return {
            "error": "missing STRIPE_CONNECT_REFRESH_URL or STRIPE_CONNECT_RETURN_URL",
        }
    stripe.api_key = STRIPE_SECRET_KEY
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=STRIPE_CONNECT_REFRESH_URL,
        return_url=STRIPE_CONNECT_RETURN_URL,
        type="account_onboarding",
    )
    return {"url": link.url}


def sync_connect_account_status(account_id: str) -> dict[str, Any] | None:
    org = get_organization_by_connect_account(account_id)
    if not org:
        return None
    if not _stripe_configured():
        return org
    stripe.api_key = STRIPE_SECRET_KEY
    account = stripe.Account.retrieve(account_id)
    charges_enabled = bool(getattr(account, "charges_enabled", False))
    payouts_enabled = bool(getattr(account, "payouts_enabled", False))
    details_submitted = bool(getattr(account, "details_submitted", False))
    status = "complete" if details_submitted and payouts_enabled else "pending"
    return upsert_org_payout_account(
        org_id=str(org["id"]),
        stripe_connect_account_id=account_id,
        payout_account_ready=charges_enabled and payouts_enabled,
        payout_onboarding_status=status,
        payouts_enabled=payouts_enabled,
    )
