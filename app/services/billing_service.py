"""Stripe Billing — platform subscriptions for org tiers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe

from app.models.campaign import update_active_campaigns_locked_tier
from app.models.org import (
    get_organization,
    update_org_billing,
    update_org_subscription,
    upsert_org_payout_account,
)
from app.utils.stripe_config import (
    STRIPE_BILLING_CANCEL_URL,
    STRIPE_BILLING_PORTAL_RETURN_URL,
    STRIPE_BILLING_SUCCESS_URL,
    STRIPE_CURRENCY,
    STRIPE_PRICE_GROW,
    STRIPE_PRICE_SCALE,
    STRIPE_PRICE_STARTER,
    STRIPE_SECRET_KEY,
)

ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}
BILLABLE_ACTIVE_STATUSES = {"active", "legacy", "trialing", "past_due"}


def tier_to_price_id(tier: int) -> str | None:
    mapping = {1: STRIPE_PRICE_STARTER, 2: STRIPE_PRICE_GROW, 3: STRIPE_PRICE_SCALE}
    price = mapping.get(int(tier))
    return price if price else None


def price_id_to_tier(price_id: str | None) -> int | None:
    if not price_id:
        return None
    mapping = {
        STRIPE_PRICE_STARTER: 1,
        STRIPE_PRICE_GROW: 2,
        STRIPE_PRICE_SCALE: 3,
    }
    return mapping.get(price_id.strip())


def org_has_active_billing(org: dict[str, Any] | None) -> bool:
    if not org:
        return False
    status = (org.get("subscription_status") or "legacy").strip().lower()
    return status in BILLABLE_ACTIVE_STATUSES


def billing_required(org: dict[str, Any] | None) -> bool:
    if not org:
        return True
    status = (org.get("subscription_status") or "legacy").strip().lower()
    return status in {"none", "canceled"}


def _stripe_configured() -> bool:
    return bool(STRIPE_SECRET_KEY)


def _tier_from_subscription(subscription: dict | Any) -> int | None:
    meta = getattr(subscription, "metadata", None) or (subscription.get("metadata") if isinstance(subscription, dict) else {}) or {}
    tier_raw = meta.get("tier")
    if tier_raw is not None:
        try:
            tier = int(tier_raw)
            if tier in (1, 2, 3):
                return tier
        except (TypeError, ValueError):
            pass
    items = getattr(subscription, "items", None)
    if items and getattr(items, "data", None):
        first = items.data[0]
        price = getattr(first, "price", None)
        price_id = getattr(price, "id", None) if price else None
        return price_id_to_tier(price_id)
    if isinstance(subscription, dict):
        data = (subscription.get("items") or {}).get("data") or []
        if data:
            price_id = (data[0].get("price") or {}).get("id")
            return price_id_to_tier(price_id)
    return None


def _period_end(subscription: dict | Any) -> datetime | None:
    ts = getattr(subscription, "current_period_end", None)
    if ts is None and isinstance(subscription, dict):
        ts = subscription.get("current_period_end")
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def _map_subscription_status(stripe_status: str | None) -> str:
    s = (stripe_status or "").strip().lower()
    if s in ACTIVE_SUBSCRIPTION_STATUSES:
        return "active"
    if s == "past_due":
        return "past_due"
    if s in {"canceled", "unpaid", "incomplete_expired"}:
        return "canceled"
    if s in {"incomplete", "paused"}:
        return "none"
    return "none"


def apply_subscription_state(org_id: str, subscription: dict | Any) -> dict[str, Any] | None:
    sub_id = getattr(subscription, "id", None) or (subscription.get("id") if isinstance(subscription, dict) else None)
    stripe_status = getattr(subscription, "status", None) or (subscription.get("status") if isinstance(subscription, dict) else None)
    mapped = _map_subscription_status(stripe_status)
    tier = _tier_from_subscription(subscription)
    period_end = _period_end(subscription)

    org = get_organization(org_id)
    if not org:
        return None

    effective_tier = tier if tier is not None else int(org.get("tier") or 1)
    if mapped != "active":
        effective_tier = 1

    updated = update_org_subscription(
        org_id,
        stripe_subscription_id=sub_id,
        subscription_status=mapped,
        subscription_current_period_end=period_end,
        tier=effective_tier if mapped == "active" else 1,
        pending_tier=None if mapped == "active" else org.get("pending_tier"),
    )
    if updated and mapped == "active" and tier is not None:
        update_active_campaigns_locked_tier(org_id, tier)
    return updated


def ensure_stripe_customer(org_id: str, email: str, name: str | None = None) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    if org.get("stripe_customer_id"):
        return {"customer_id": org["stripe_customer_id"]}
    if not _stripe_configured():
        return {"error": "Stripe is not configured"}
    stripe.api_key = STRIPE_SECRET_KEY
    customer = stripe.Customer.create(
        email=email,
        name=name or org.get("name"),
        metadata={"org_id": org_id},
    )
    update_org_billing(org_id, stripe_customer_id=customer.id)
    return {"customer_id": customer.id}


def ensure_connect_account(org_id: str, email: str) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    if org.get("stripe_connect_account_id"):
        return {"connect_account_id": org["stripe_connect_account_id"]}
    if not _stripe_configured():
        return {"error": "Stripe is not configured"}
    stripe.api_key = STRIPE_SECRET_KEY
    account = stripe.Account.create(
        type="express",
        country="CA",
        email=email,
        capabilities={
            "transfers": {"requested": True},
        },
        metadata={"org_id": org_id},
    )
    upsert_org_payout_account(
        org_id=org_id,
        stripe_connect_account_id=account.id,
        payout_onboarding_status="pending",
        payout_account_ready=False,
        payouts_enabled=False,
    )
    return {"connect_account_id": account.id}


def setup_billing(org_id: str, email: str, name: str | None = None) -> dict[str, Any]:
    customer = ensure_stripe_customer(org_id, email, name)
    if customer.get("error"):
        return customer
    connect = ensure_connect_account(org_id, email)
    if connect.get("error"):
        return connect
    return {
        "customer_id": customer["customer_id"],
        "connect_account_id": connect["connect_account_id"],
    }


def create_subscription_checkout(org_id: str, tier: int, owner_email: str) -> dict[str, Any]:
    tier = int(tier) if tier in (1, 2, 3) else 1
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    price_id = tier_to_price_id(tier)
    if not price_id:
        return {"error": "Stripe price not configured for this tier"}
    if not STRIPE_BILLING_SUCCESS_URL or not STRIPE_BILLING_CANCEL_URL:
        return {"error": "missing STRIPE_BILLING_SUCCESS_URL or STRIPE_BILLING_CANCEL_URL"}
    if not _stripe_configured():
        return {"error": "Stripe is not configured"}

    setup = setup_billing(org_id, owner_email, org.get("name"))
    if setup.get("error"):
        return setup

    stripe.api_key = STRIPE_SECRET_KEY
    update_org_billing(org_id, pending_tier=tier)

    session = stripe.checkout.Session.create(
        customer=setup["customer_id"],
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{STRIPE_BILLING_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=STRIPE_BILLING_CANCEL_URL,
        metadata={"org_id": org_id, "tier": str(tier)},
        subscription_data={
            "metadata": {"org_id": org_id, "tier": str(tier)},
        },
        currency=STRIPE_CURRENCY,
    )
    return {"url": session.url, "session_id": session.id}


def change_subscription_tier(org_id: str, new_tier: int, owner_email: str) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    new_tier = int(new_tier) if new_tier in (1, 2, 3) else 1
    sub_id = org.get("stripe_subscription_id")
    status = (org.get("subscription_status") or "").strip().lower()
    price_id = tier_to_price_id(new_tier)
    if not price_id:
        return {"error": "Stripe price not configured for this tier"}

    if not sub_id or status not in {"active", "past_due", "trialing"}:
        return create_subscription_checkout(org_id, new_tier, owner_email)

    if not _stripe_configured():
        return {"error": "Stripe is not configured"}

    stripe.api_key = STRIPE_SECRET_KEY
    subscription = stripe.Subscription.retrieve(sub_id)
    item_id = subscription["items"]["data"][0]["id"]
    updated_sub = stripe.Subscription.modify(
        sub_id,
        items=[{"id": item_id, "price": price_id}],
        proration_behavior="create_prorations",
        metadata={"org_id": org_id, "tier": str(new_tier)},
    )
    result = apply_subscription_state(org_id, updated_sub)
    return {"subscription_id": updated_sub.id, "tier": result.get("tier") if result else new_tier}


def create_billing_portal_session(org_id: str) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    customer_id = org.get("stripe_customer_id")
    if not customer_id:
        return {"error": "no Stripe customer on file"}
    if not STRIPE_BILLING_PORTAL_RETURN_URL:
        return {"error": "missing STRIPE_BILLING_PORTAL_RETURN_URL"}
    if not _stripe_configured():
        return {"error": "Stripe is not configured"}
    stripe.api_key = STRIPE_SECRET_KEY
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=STRIPE_BILLING_PORTAL_RETURN_URL,
    )
    return {"url": session.url}


def get_billing_status(org_id: str) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    return {
        "org_id": org_id,
        "tier": org.get("tier"),
        "pending_tier": org.get("pending_tier"),
        "subscription_status": org.get("subscription_status"),
        "subscription_current_period_end": (
            org["subscription_current_period_end"].isoformat()
            if org.get("subscription_current_period_end")
            else None
        ),
        "stripe_customer_id": org.get("stripe_customer_id"),
        "stripe_subscription_id": org.get("stripe_subscription_id"),
        "stripe_connect_account_id": org.get("stripe_connect_account_id"),
        "payouts_enabled": bool(org.get("payouts_enabled")),
        "payout_account_ready": bool(org.get("payout_account_ready")),
        "payout_onboarding_status": org.get("payout_onboarding_status"),
        "billing_required": billing_required(org),
        "billing_active": org_has_active_billing(org),
    }


def handle_checkout_session_completed(session: dict | Any) -> None:
    meta = getattr(session, "metadata", None) or (session.get("metadata") if isinstance(session, dict) else {}) or {}
    org_id = meta.get("org_id")
    if not org_id:
        return
    sub_id = getattr(session, "subscription", None) or (session.get("subscription") if isinstance(session, dict) else None)
    customer_id = getattr(session, "customer", None) or (session.get("customer") if isinstance(session, dict) else None)
    if customer_id:
        update_org_billing(str(org_id), stripe_customer_id=str(customer_id))
    if not sub_id or not _stripe_configured():
        return
    stripe.api_key = STRIPE_SECRET_KEY
    subscription = stripe.Subscription.retrieve(str(sub_id))
    apply_subscription_state(str(org_id), subscription)


def handle_subscription_event(subscription: dict | Any) -> None:
    meta = getattr(subscription, "metadata", None) or (subscription.get("metadata") if isinstance(subscription, dict) else {}) or {}
    org_id = meta.get("org_id")
    if not org_id:
        customer_id = getattr(subscription, "customer", None) or (subscription.get("customer") if isinstance(subscription, dict) else None)
        if customer_id:
            from app.models.org import get_organization_by_stripe_customer
            org = get_organization_by_stripe_customer(str(customer_id))
            org_id = org.get("id") if org else None
    if not org_id:
        return
    apply_subscription_state(str(org_id), subscription)


def handle_invoice_paid(invoice: dict | Any) -> None:
    sub_id = getattr(invoice, "subscription", None) or (invoice.get("subscription") if isinstance(invoice, dict) else None)
    if not sub_id or not _stripe_configured():
        return
    stripe.api_key = STRIPE_SECRET_KEY
    subscription = stripe.Subscription.retrieve(str(sub_id))
    handle_subscription_event(subscription)


def handle_invoice_payment_failed(invoice: dict | Any) -> None:
    sub_id = getattr(invoice, "subscription", None) or (invoice.get("subscription") if isinstance(invoice, dict) else None)
    customer_id = getattr(invoice, "customer", None) or (invoice.get("customer") if isinstance(invoice, dict) else None)
    org_id = None
    if customer_id:
        from app.models.org import get_organization_by_stripe_customer
        org = get_organization_by_stripe_customer(str(customer_id))
        org_id = org.get("id") if org else None
    if org_id:
        update_org_subscription(str(org_id), subscription_status="past_due")
    elif sub_id and _stripe_configured():
        stripe.api_key = STRIPE_SECRET_KEY
        subscription = stripe.Subscription.retrieve(str(sub_id))
        handle_subscription_event(subscription)
