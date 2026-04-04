import os
import math
import stripe
import uuid
from typing import Dict, Any
from app.models.campaign import get_campaign
from app.models.donation import create_donation, set_payment_intent
from app.services.fee_policy_service import (
    FEE_POLICY_VERSION,
    build_donation_accounting,
    estimate_stripe_processing_fee_cents,
    normalize_fee_option,
)

CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")


def _to_cents(amount: float) -> int:
    return int(math.floor(amount * 100 + 0.5))


def start_checkout(
    *,
    campaign_id: str,
    amount: float,
    donor_email: str | None = None,
    message: str | None = None,
) -> Dict[str, Any]:
    camp = get_campaign(campaign_id)
    if not camp:
        return {"error": "campaign not found"}

    amount_cents = _to_cents(amount)
    if amount_cents <= 0:
        return {"error": "amount must be > 0"}

    donation = create_donation(
        org_id=camp["org_id"],
        campaign_id=campaign_id,
        amount_cents=amount_cents,
        currency=CURRENCY,
        donor_email=(donor_email or None),
        message=(message or None),
    )
    fee_option = normalize_fee_option(camp.get("fee_option"))
    stripe_fee_estimate = estimate_stripe_processing_fee_cents(amount_cents)
    checkout_accounting = build_donation_accounting(
        fee_option=fee_option,
        campaign_total_dollars=float(camp.get("total_raised") or 0),
        amount_cents=amount_cents,
        stripe_processing_fee_cents=stripe_fee_estimate,
    )

    if not STRIPE_SECRET:
        fake_pi = f"pi_{uuid.uuid4().hex}"
        fake_cs = f"{fake_pi}_secret_{uuid.uuid4().hex}"
        set_payment_intent(donation["id"], fake_pi)
        return {
            "donation_id": donation["id"],
            "clientSecret": fake_cs,
            "dev_mode": True,
            "fee_option": fee_option,
            "fee_preview": {
                "platform_fee_percent": checkout_accounting.platform_fee_percent,
                "platform_fee_cents": checkout_accounting.platform_fee_cents,
                "estimated_stripe_fee_cents": checkout_accounting.stripe_processing_fee_cents,
                "estimated_net_to_org_cents": checkout_accounting.net_to_org_cents,
            },
        }

    stripe.api_key = STRIPE_SECRET
    pi_payload: Dict[str, Any] = {
        "amount": amount_cents,
        "currency": CURRENCY,
        "metadata": {
            "donation_id": donation["id"],
            "campaign_id": campaign_id,
            "org_id": camp["org_id"],
            "fee_option": fee_option,
            "fee_policy_version": camp.get("fee_policy_version") or FEE_POLICY_VERSION,
        },
        "idempotency_key": donation["id"],
        "automatic_payment_methods": {"enabled": True},
    }

    pi = stripe.PaymentIntent.create(**pi_payload)

    set_payment_intent(donation["id"], pi.id)
    return {
        "donation_id": donation["id"],
        "clientSecret": pi.client_secret,
        "fee_option": fee_option,
        "fee_preview": {
            "platform_fee_percent": checkout_accounting.platform_fee_percent,
            "platform_fee_cents": checkout_accounting.platform_fee_cents,
            "estimated_stripe_fee_cents": checkout_accounting.stripe_processing_fee_cents,
            "estimated_net_to_org_cents": checkout_accounting.net_to_org_cents,
        },
    }
