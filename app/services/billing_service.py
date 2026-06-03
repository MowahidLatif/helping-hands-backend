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
    STRIPE_PAYMENT_GRACE_DAYS,
    STRIPE_PRICE_GROW_ANNUAL,
    STRIPE_PRICE_GROW_MONTHLY,
    STRIPE_PRICE_SCALE_ANNUAL,
    STRIPE_PRICE_SCALE_MONTHLY,
    STRIPE_PRICE_STARTER_ANNUAL,
    STRIPE_PRICE_STARTER_MONTHLY,
    STRIPE_SECRET_KEY,
    STRIPE_TRIAL_DAYS,
)

BILLABLE_ACTIVE_STATUSES = {"active", "legacy", "trialing", "past_due"}

# Display amounts (CAD) — must match Stripe Prices
TIER_CHARGE_MONTHLY: dict[int, int] = {1: 10, 2: 40, 3: 100}
TIER_CHARGE_ANNUAL: dict[int, int] = {1: 100, 2: 400, 3: 1000}


def _normalize_interval(interval: str | None) -> str:
    iv = (interval or "monthly").strip().lower()
    return "annual" if iv == "annual" else "monthly"


def tier_to_price_id(tier: int, interval: str | None = "monthly") -> str | None:
    tier = int(tier) if tier in (1, 2, 3) else 1
    iv = _normalize_interval(interval)
    mapping = {
        (1, "monthly"): STRIPE_PRICE_STARTER_MONTHLY,
        (1, "annual"): STRIPE_PRICE_STARTER_ANNUAL,
        (2, "monthly"): STRIPE_PRICE_GROW_MONTHLY,
        (2, "annual"): STRIPE_PRICE_GROW_ANNUAL,
        (3, "monthly"): STRIPE_PRICE_SCALE_MONTHLY,
        (3, "annual"): STRIPE_PRICE_SCALE_ANNUAL,
    }
    price = mapping.get((tier, iv))
    return price if price else None


def _build_price_id_map() -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    for tier in (1, 2, 3):
        for iv in ("monthly", "annual"):
            pid = tier_to_price_id(tier, iv)
            if pid:
                out[pid.strip()] = (tier, iv)
    return out


def price_id_to_tier(price_id: str | None) -> int | None:
    if not price_id:
        return None
    tier_interval = _build_price_id_map().get(price_id.strip())
    return tier_interval[0] if tier_interval else None


def price_id_to_tier_and_interval(price_id: str | None) -> tuple[int, str] | None:
    if not price_id:
        return None
    return _build_price_id_map().get(price_id.strip())


def charge_amount_for_tier(tier: int, interval: str | None) -> int:
    tier = int(tier) if tier in (1, 2, 3) else 1
    if _normalize_interval(interval) == "annual":
        return TIER_CHARGE_ANNUAL.get(tier, 100)
    return TIER_CHARGE_MONTHLY.get(tier, 10)


def is_trial_eligible(org: dict[str, Any] | None) -> bool:
    if not org or STRIPE_TRIAL_DAYS <= 0:
        return False
    status = (org.get("subscription_status") or "none").strip().lower()
    return status == "none"


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
    if s == "trialing":
        return "trialing"
    if s == "active":
        return "active"
    if s == "past_due":
        return "past_due"
    if s in {"canceled", "unpaid", "incomplete_expired"}:
        return "canceled"
    if s in {"incomplete", "paused"}:
        return "none"
    return "none"


def _trial_end(subscription: dict | Any) -> datetime | None:
    ts = getattr(subscription, "trial_end", None)
    if ts is None and isinstance(subscription, dict):
        ts = subscription.get("trial_end")
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def _interval_from_subscription(subscription: dict | Any) -> str | None:
    meta = getattr(subscription, "metadata", None) or (
        subscription.get("metadata") if isinstance(subscription, dict) else {}
    ) or {}
    iv = (meta.get("interval") or "").strip().lower()
    if iv in ("monthly", "annual"):
        return iv
    items = getattr(subscription, "items", None)
    if items and getattr(items, "data", None):
        first = items.data[0]
        price = getattr(first, "price", None)
        recurring = getattr(price, "recurring", None) if price else None
        if recurring:
            interval = getattr(recurring, "interval", None)
            if interval == "year":
                return "annual"
            if interval == "month":
                return "monthly"
    if isinstance(subscription, dict):
        data = (subscription.get("items") or {}).get("data") or []
        if data:
            recurring = (data[0].get("price") or {}).get("recurring") or {}
            if recurring.get("interval") == "year":
                return "annual"
            if recurring.get("interval") == "month":
                return "monthly"
            price_id = (data[0].get("price") or {}).get("id")
            ti = price_id_to_tier_and_interval(price_id)
            if ti:
                return ti[1]
    return None


def _cancel_at(subscription: dict | Any) -> datetime | None:
    ts = getattr(subscription, "cancel_at", None)
    if ts is None and isinstance(subscription, dict):
        ts = subscription.get("cancel_at")
    if not ts:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


def _cancel_at_period_end(subscription: dict | Any) -> bool:
    val = getattr(subscription, "cancel_at_period_end", None)
    if val is None and isinstance(subscription, dict):
        val = subscription.get("cancel_at_period_end")
    return bool(val)


def apply_subscription_state(org_id: str, subscription: dict | Any) -> dict[str, Any] | None:
    sub_id = getattr(subscription, "id", None) or (subscription.get("id") if isinstance(subscription, dict) else None)
    stripe_status = getattr(subscription, "status", None) or (subscription.get("status") if isinstance(subscription, dict) else None)
    mapped = _map_subscription_status(stripe_status)
    tier = _tier_from_subscription(subscription)
    period_end = _period_end(subscription)
    cancel_at_period_end = _cancel_at_period_end(subscription)
    cancel_at = _cancel_at(subscription)
    trial_end = _trial_end(subscription)
    billing_interval = _interval_from_subscription(subscription)

    org = get_organization(org_id)
    if not org:
        return None

    has_paid_access = mapped in {"active", "trialing"}
    effective_tier = tier if tier is not None else int(org.get("tier") or 1)
    if not has_paid_access:
        effective_tier = 1

    clear_trial = mapped not in {"trialing"}
    clear_grace = mapped not in {"past_due"}

    updated = update_org_subscription(
        org_id,
        stripe_subscription_id=sub_id,
        subscription_status=mapped,
        subscription_current_period_end=period_end,
        tier=effective_tier if has_paid_access else 1,
        pending_tier=None if has_paid_access else org.get("pending_tier"),
        subscription_cancel_at_period_end=cancel_at_period_end if mapped == "active" else False,
        subscription_cancel_at=cancel_at if mapped == "active" and cancel_at_period_end else None,
        billing_interval=billing_interval or org.get("billing_interval"),
        trial_ends_at=trial_end if mapped == "trialing" else (None if clear_trial else ...),
        payment_grace_ends_at=None if clear_grace else ...,
    )
    if updated and has_paid_access and tier is not None:
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


def create_subscription_checkout(
    org_id: str,
    tier: int,
    owner_email: str,
    *,
    interval: str | None = "monthly",
) -> dict[str, Any]:
    tier = int(tier) if tier in (1, 2, 3) else 1
    iv = _normalize_interval(interval)
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    price_id = tier_to_price_id(tier, iv)
    if not price_id:
        return {"error": "Stripe price not configured for this tier and interval"}
    if not STRIPE_BILLING_SUCCESS_URL or not STRIPE_BILLING_CANCEL_URL:
        return {"error": "missing STRIPE_BILLING_SUCCESS_URL or STRIPE_BILLING_CANCEL_URL"}
    if not _stripe_configured():
        return {"error": "Stripe is not configured"}

    setup = setup_billing(org_id, owner_email, org.get("name"))
    if setup.get("error"):
        return setup

    stripe.api_key = STRIPE_SECRET_KEY
    update_org_billing(org_id, pending_tier=tier, billing_interval=iv)

    sub_meta = {"org_id": org_id, "tier": str(tier), "interval": iv}
    subscription_data: dict[str, Any] = {"metadata": sub_meta}
    trial_eligible = is_trial_eligible(org)
    if trial_eligible:
        subscription_data["trial_period_days"] = STRIPE_TRIAL_DAYS

    session = stripe.checkout.Session.create(
        customer=setup["customer_id"],
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{STRIPE_BILLING_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=STRIPE_BILLING_CANCEL_URL,
        metadata=sub_meta,
        subscription_data=subscription_data,
        payment_method_collection="always",
        currency=STRIPE_CURRENCY,
    )
    return {
        "url": session.url,
        "session_id": session.id,
        "trial_eligible": trial_eligible,
        "trial_days": STRIPE_TRIAL_DAYS if trial_eligible else 0,
        "interval": iv,
    }


def change_subscription_tier(org_id: str, new_tier: int, owner_email: str) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    new_tier = int(new_tier) if new_tier in (1, 2, 3) else 1
    sub_id = org.get("stripe_subscription_id")
    status = (org.get("subscription_status") or "").strip().lower()
    iv = _normalize_interval(org.get("billing_interval"))
    price_id = tier_to_price_id(new_tier, iv)
    if not price_id:
        return {"error": "Stripe price not configured for this tier"}

    if not sub_id or status not in {"active", "past_due", "trialing"}:
        return create_subscription_checkout(org_id, new_tier, owner_email, interval=iv)

    if not _stripe_configured():
        return {"error": "Stripe is not configured"}

    stripe.api_key = STRIPE_SECRET_KEY
    subscription = stripe.Subscription.retrieve(sub_id)
    item_id = subscription["items"]["data"][0]["id"]
    updated_sub = stripe.Subscription.modify(
        sub_id,
        items=[{"id": item_id, "price": price_id}],
        proration_behavior="create_prorations",
        metadata={"org_id": org_id, "tier": str(new_tier), "interval": iv},
    )
    result = apply_subscription_state(org_id, updated_sub)
    return {"subscription_id": updated_sub.id, "tier": result.get("tier") if result else new_tier}


def cancel_subscription(org_id: str) -> dict[str, Any]:
    org = get_organization(org_id)
    if not org:
        return {"error": "organization not found"}
    sub_id = org.get("stripe_subscription_id")
    status = (org.get("subscription_status") or "").strip().lower()
    if not sub_id or status not in {"active", "past_due", "trialing"}:
        return {"error": "no active subscription to cancel"}
    if not _stripe_configured():
        return {"error": "Stripe is not configured"}

    stripe.api_key = STRIPE_SECRET_KEY
    canceled_sub = stripe.Subscription.cancel(str(sub_id))
    result = apply_subscription_state(org_id, canceled_sub)
    return {
        "subscription_id": canceled_sub.id,
        "subscription_status": result.get("subscription_status") if result else "canceled",
        "tier": result.get("tier") if result else 1,
    }


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
    status = (org.get("subscription_status") or "legacy").strip().lower()
    can_cancel = status in {"active", "past_due", "trialing"} and bool(org.get("stripe_subscription_id"))
    can_change_tier = status in {"active", "past_due", "trialing", "none", "canceled", "legacy"}
    is_trialing = status == "trialing"
    trial_ends = org.get("trial_ends_at")
    trial_days_remaining = None
    if is_trialing and trial_ends:
        if trial_ends.tzinfo is None:
            trial_ends = trial_ends.replace(tzinfo=timezone.utc)
        delta = trial_ends - datetime.now(timezone.utc)
        trial_days_remaining = max(0, delta.days)
    tier = int(org.get("tier") or 1)
    interval = org.get("billing_interval") or "monthly"
    return {
        "org_id": org_id,
        "tier": tier,
        "pending_tier": org.get("pending_tier"),
        "subscription_status": org.get("subscription_status"),
        "subscription_current_period_end": (
            org["subscription_current_period_end"].isoformat()
            if org.get("subscription_current_period_end")
            else None
        ),
        "subscription_cancel_at_period_end": bool(org.get("subscription_cancel_at_period_end")),
        "subscription_cancel_at": (
            org["subscription_cancel_at"].isoformat()
            if org.get("subscription_cancel_at")
            else None
        ),
        "billing_interval": interval,
        "trial_ends_at": trial_ends.isoformat() if trial_ends else None,
        "payment_grace_ends_at": (
            org["payment_grace_ends_at"].isoformat()
            if org.get("payment_grace_ends_at")
            else None
        ),
        "is_trialing": is_trialing,
        "trial_days_remaining": trial_days_remaining,
        "next_charge_amount": charge_amount_for_tier(tier, interval),
        "next_charge_currency": STRIPE_CURRENCY.upper(),
        "trial_eligible": is_trial_eligible(org),
        "stripe_customer_id": org.get("stripe_customer_id"),
        "stripe_subscription_id": org.get("stripe_subscription_id"),
        "stripe_connect_account_id": org.get("stripe_connect_account_id"),
        "payouts_enabled": bool(org.get("payouts_enabled")),
        "payout_account_ready": bool(org.get("payout_account_ready")),
        "payout_onboarding_status": org.get("payout_onboarding_status"),
        "billing_required": billing_required(org),
        "billing_active": org_has_active_billing(org),
        "can_cancel": can_cancel,
        "can_change_tier": can_change_tier,
    }


def handle_checkout_session_completed(session: dict | Any) -> None:
    meta = getattr(session, "metadata", None) or (session.get("metadata") if isinstance(session, dict) else {}) or {}
    org_id = meta.get("org_id")
    if not org_id:
        return
    sub_id = getattr(session, "subscription", None) or (session.get("subscription") if isinstance(session, dict) else None)
    customer_id = getattr(session, "customer", None) or (session.get("customer") if isinstance(session, dict) else None)
    interval = _normalize_interval(meta.get("interval"))
    if customer_id:
        update_org_billing(
            str(org_id),
            stripe_customer_id=str(customer_id),
            billing_interval=interval,
        )
    if not sub_id or not _stripe_configured():
        return
    stripe.api_key = STRIPE_SECRET_KEY
    subscription = stripe.Subscription.retrieve(str(sub_id))
    updated = apply_subscription_state(str(org_id), subscription)
    stripe_status = getattr(subscription, "status", None) or (
        subscription.get("status") if isinstance(subscription, dict) else None
    )
    if updated and stripe_status == "trialing":
        from app.services.billing_email_service import send_trial_started_email
        send_trial_started_email(str(org_id))


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
    amount_paid = getattr(invoice, "amount_paid", None) or (
        invoice.get("amount_paid") if isinstance(invoice, dict) else 0
    )
    stripe.api_key = STRIPE_SECRET_KEY
    subscription = stripe.Subscription.retrieve(str(sub_id))
    handle_subscription_event(subscription)
    if int(amount_paid or 0) > 0:
        from app.services.billing_email_service import send_subscription_welcome_email
        meta = getattr(subscription, "metadata", None) or subscription.get("metadata") or {}
        org_id = meta.get("org_id")
        if not org_id:
            customer_id = getattr(subscription, "customer", None) or subscription.get("customer")
            if customer_id:
                from app.models.org import get_organization_by_stripe_customer
                org = get_organization_by_stripe_customer(str(customer_id))
                org_id = org.get("id") if org else None
        if org_id:
            send_subscription_welcome_email(str(org_id), int(amount_paid))


def handle_invoice_payment_failed(invoice: dict | Any) -> None:
    from datetime import timedelta

    sub_id = getattr(invoice, "subscription", None) or (invoice.get("subscription") if isinstance(invoice, dict) else None)
    customer_id = getattr(invoice, "customer", None) or (invoice.get("customer") if isinstance(invoice, dict) else None)
    org_id = None
    org = None
    if customer_id:
        from app.models.org import get_organization_by_stripe_customer
        org = get_organization_by_stripe_customer(str(customer_id))
        org_id = org.get("id") if org else None
    if org_id and org:
        grace_end = datetime.now(timezone.utc) + timedelta(days=STRIPE_PAYMENT_GRACE_DAYS)
        update_org_subscription(
            str(org_id),
            subscription_status="past_due",
            payment_grace_ends_at=grace_end,
        )
        from app.services.billing_email_service import send_payment_failed_email
        send_payment_failed_email(str(org_id))
    elif sub_id and _stripe_configured():
        stripe.api_key = STRIPE_SECRET_KEY
        subscription = stripe.Subscription.retrieve(str(sub_id))
        handle_subscription_event(subscription)


def handle_subscription_trial_will_end(subscription: dict | Any) -> None:
    meta = getattr(subscription, "metadata", None) or (
        subscription.get("metadata") if isinstance(subscription, dict) else {}
    ) or {}
    org_id = meta.get("org_id")
    if not org_id:
        customer_id = getattr(subscription, "customer", None) or (
            subscription.get("customer") if isinstance(subscription, dict) else None
        )
        if customer_id:
            from app.models.org import get_organization_by_stripe_customer
            org = get_organization_by_stripe_customer(str(customer_id))
            org_id = org.get("id") if org else None
    if org_id:
        from app.services.billing_email_service import send_trial_ending_soon_email
        send_trial_ending_soon_email(str(org_id), days_remaining=3)


def process_trial_day6_reminders() -> int:
    """Send 'trial ends tomorrow' emails for orgs whose trial ends in ~24–48h."""
    from app.services.billing_email_service import send_trial_ends_tomorrow_email
    from app.utils.db import get_db_connection

    sql = """
        SELECT id FROM organizations
        WHERE subscription_status = 'trialing'
          AND trial_ends_at IS NOT NULL
          AND trial_ends_at > now() + interval '20 hours'
          AND trial_ends_at <= now() + interval '52 hours'
    """
    sent = 0
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    for (org_id,) in rows:
        if send_trial_ends_tomorrow_email(str(org_id)):
            sent += 1
    return sent


def process_payment_grace_expiry() -> int:
    """Restrict orgs still past_due after grace period."""
    from app.utils.db import get_db_connection

    sql = """
        SELECT id, stripe_subscription_id FROM organizations
        WHERE subscription_status = 'past_due'
          AND payment_grace_ends_at IS NOT NULL
          AND payment_grace_ends_at < now()
    """
    restricted = 0
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    for org_id, sub_id in rows:
        update_org_subscription(
            str(org_id),
            subscription_status="canceled",
            tier=1,
            payment_grace_ends_at=None,
        )
        if sub_id and _stripe_configured():
            try:
                stripe.api_key = STRIPE_SECRET_KEY
                stripe.Subscription.cancel(str(sub_id))
            except Exception:
                pass
        from app.services.billing_email_service import send_grace_period_expired_email
        send_grace_period_expired_email(str(org_id))
        restricted += 1
    return restricted
