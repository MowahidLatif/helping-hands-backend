"""Billing lifecycle emails (trial, conversion, payment failure)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.models.billing_email_log import billing_email_already_sent, record_billing_email_sent
from app.models.org import get_organization
from app.services.billing_service import charge_amount_for_tier
from app.utils.email_sender import send_email
from app.utils.tier_features import TIER_LIMITS

EMAIL_TYPES = {
    "trial_started": "trial_started",
    "trial_ending_3d": "trial_ending_3d",
    "trial_ends_tomorrow": "trial_ends_tomorrow",
    "subscription_welcome": "subscription_welcome",
    "payment_failed": "payment_failed",
    "grace_expired": "grace_expired",
}


def _owner_email(org: dict[str, Any]) -> str | None:
    from app.models.org_user import list_org_user_ids_by_roles
    from app.models.user import get_user_by_id

    owner_ids = list_org_user_ids_by_roles(org["id"], ["owner"])
    if not owner_ids:
        return None
    user = get_user_by_id(owner_ids[0])
    return user.get("email") if user else None


def _format_date(dt: datetime | None) -> str:
    if not dt:
        return "soon"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%B %d, %Y")


def _send_billing_email(
    org_id: str,
    email_type: str,
    subject: str,
    text: str,
    html: str | None = None,
) -> bool:
    if billing_email_already_sent(org_id, email_type):
        return False
    org = get_organization(org_id)
    if not org:
        return False
    to = _owner_email(org)
    if not to:
        return False
    provider, err = send_email(
        to_email=to,
        subject=subject,
        body_text=text,
        body_html=html or f"<p>{text}</p>",
    )
    if provider:
        record_billing_email_sent(org_id, email_type)
        return True
    return False


def send_trial_started_email(org_id: str) -> bool:
    org = get_organization(org_id)
    if not org:
        return False
    tier = int(org.get("tier") or org.get("pending_tier") or 1)
    plan = TIER_LIMITS.get(tier, {}).get("name", "Starter")
    trial_end = _format_date(org.get("trial_ends_at"))
    settings_url = f"{os.getenv('FRONTEND_URL', '').rstrip('/')}/settings"
    text = (
        f"Your 7-day free trial on the {plan} plan has started. "
        f"You will not be charged until {trial_end}. "
        f"Cancel anytime before then from Settings: {settings_url}"
    )
    return _send_billing_email(
        org_id,
        EMAIL_TYPES["trial_started"],
        f"Your HelpingHandsFund trial has started — no charge until {trial_end}",
        text,
    )


def send_trial_ending_soon_email(org_id: str, *, days_remaining: int = 3) -> bool:
    org = get_organization(org_id)
    if not org:
        return False
    tier = int(org.get("tier") or 1)
    plan = TIER_LIMITS.get(tier, {}).get("name", "Starter")
    trial_end = _format_date(org.get("trial_ends_at"))
    amount = charge_amount_for_tier(tier, org.get("billing_interval"))
    interval = org.get("billing_interval") or "monthly"
    period = "year" if interval == "annual" else "month"
    text = (
        f"Your {plan} trial ends in about {days_remaining} days ({trial_end}). "
        f"When it converts, you'll be charged ${amount}/{period}. "
        f"Manage or cancel your subscription in Settings."
    )
    return _send_billing_email(
        org_id,
        EMAIL_TYPES["trial_ending_3d"],
        f"{days_remaining} days left on your HelpingHandsFund trial",
        text,
    )


def send_trial_ends_tomorrow_email(org_id: str) -> bool:
    org = get_organization(org_id)
    if not org:
        return False
    tier = int(org.get("tier") or 1)
    plan = TIER_LIMITS.get(tier, {}).get("name", "Starter")
    trial_end = _format_date(org.get("trial_ends_at"))
    amount = charge_amount_for_tier(tier, org.get("billing_interval"))
    interval = org.get("billing_interval") or "monthly"
    period = "year" if interval == "annual" else "month"
    text = (
        f"Your trial ends tomorrow ({trial_end}). "
        f"You'll be charged ${amount}/{period} for {plan} unless you cancel first. "
        f"Go to Settings to cancel or update your payment method."
    )
    return _send_billing_email(
        org_id,
        EMAIL_TYPES["trial_ends_tomorrow"],
        f"Your trial ends tomorrow — ${amount} charge on {trial_end}",
        text,
    )


def send_subscription_welcome_email(org_id: str, amount_paid_cents: int) -> bool:
    org = get_organization(org_id)
    if not org:
        return False
    tier = int(org.get("tier") or 1)
    plan = TIER_LIMITS.get(tier, {}).get("name", "Starter")
    amount = amount_paid_cents / 100.0
    text = (
        f"Welcome to HelpingHandsFund {plan}! "
        f"Your subscription is now active. Payment received: ${amount:.2f}. "
        f"Thank you for subscribing."
    )
    return _send_billing_email(
        org_id,
        EMAIL_TYPES["subscription_welcome"],
        f"Welcome to HelpingHandsFund {plan}",
        text,
    )


def send_payment_failed_email(org_id: str) -> bool:
    org = get_organization(org_id)
    if not org:
        return False
    grace = _format_date(org.get("payment_grace_ends_at"))
    settings_url = f"{os.getenv('FRONTEND_URL', '').rstrip('/')}/settings"
    text = (
        f"Your latest subscription payment did not go through. "
        f"Update your card in Settings ({settings_url}) before {grace} "
        f"to keep full access."
    )
    return _send_billing_email(
        org_id,
        EMAIL_TYPES["payment_failed"],
        "Action required: update your payment method",
        text,
    )


def send_grace_period_expired_email(org_id: str) -> bool:
    settings_url = f"{os.getenv('FRONTEND_URL', '').rstrip('/')}/settings"
    text = (
        f"Your account has been restricted because we could not process your subscription payment. "
        f"Update your payment method at {settings_url} to restore access."
    )
    return _send_billing_email(
        org_id,
        EMAIL_TYPES["grace_expired"],
        "Your HelpingHandsFund account is restricted",
        text,
    )
