import os
import math
import uuid
from typing import Dict, Any
from app.models.campaign import get_campaign
from app.models.donation import create_donation, set_payment_intent

CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")


def _to_cents(amount: float) -> int:
    return int(math.floor(amount * 100 + 0.5))


def start_checkout(
    *, campaign_id: str, amount: float, donor_email: str | None = None
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
    )

    # Dev fallback (no Stripe key provided)
    if not STRIPE_SECRET:
        fake_pi = f"pi_{uuid.uuid4().hex}"
        fake_cs = f"{fake_pi}_secret_{uuid.uuid4().hex}"
        set_payment_intent(donation["id"], fake_pi)
        return {
            "donation_id": donation["id"],
            "clientSecret": fake_cs,
            "dev_mode": True,
        }

    # Real Stripe
    import stripe

    stripe.api_key = STRIPE_SECRET

    pi = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=CURRENCY,
        metadata={
            "donation_id": donation["id"],
            "campaign_id": campaign_id,
            "org_id": camp["org_id"],
        },
        idempotency_key=donation["id"],
        automatic_payment_methods={"enabled": True},
    )

    set_payment_intent(donation["id"], pi.id)
    return {"donation_id": donation["id"], "clientSecret": pi.client_secret}


# def create_donation(data):
#     return insert_donation(data)

# def get_donations_for_campaign(campaign_id):
#     return select_donations_by_campaign(campaign_id)
