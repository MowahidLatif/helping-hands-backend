import os
import math
import stripe
import uuid
from typing import Dict, Any
from app.models.campaign import get_campaign
from app.models.donation import create_donation, set_payment_intent

CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_CONNECT_DESTINATION_ACCOUNT = os.getenv(
    "STRIPE_CONNECT_DESTINATION_ACCOUNT_ID", ""
).strip()
try:
    APPLICATION_FEE_PERCENT = float(
        os.getenv("STRIPE_APPLICATION_FEE_PERCENT", "0") or "0"
    )
except ValueError:
    APPLICATION_FEE_PERCENT = 0.0


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

    if not STRIPE_SECRET:
        fake_pi = f"pi_{uuid.uuid4().hex}"
        fake_cs = f"{fake_pi}_secret_{uuid.uuid4().hex}"
        set_payment_intent(donation["id"], fake_pi)
        return {
            "donation_id": donation["id"],
            "clientSecret": fake_cs,
            "dev_mode": True,
        }

    stripe.api_key = STRIPE_SECRET
    pi_payload: Dict[str, Any] = {
        "amount": amount_cents,
        "currency": CURRENCY,
        "metadata": {
            "donation_id": donation["id"],
            "campaign_id": campaign_id,
            "org_id": camp["org_id"],
        },
        "idempotency_key": donation["id"],
        "automatic_payment_methods": {"enabled": True},
    }

    if STRIPE_CONNECT_DESTINATION_ACCOUNT:
        pi_payload["transfer_data"] = {
            "destination": STRIPE_CONNECT_DESTINATION_ACCOUNT
        }
        if APPLICATION_FEE_PERCENT > 0:
            fee_amount = int(
                math.floor(amount_cents * (APPLICATION_FEE_PERCENT / 100.0))
            )
            if fee_amount > 0:
                pi_payload["application_fee_amount"] = fee_amount

    pi = stripe.PaymentIntent.create(**pi_payload)

    set_payment_intent(donation["id"], pi.id)
    return {"donation_id": donation["id"], "clientSecret": pi.client_secret}
