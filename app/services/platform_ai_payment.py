"""
Optional Stripe PaymentIntent before AI site generation (platform revenue, not campaign donation).
"""

from __future__ import annotations

import os
import uuid

import stripe

STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")
CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")
DEFAULT_AMOUNT_CENTS = int(os.getenv("STRIPE_AI_GENERATION_AMOUNT_CENTS", "500"))


def require_payment_for_ai() -> bool:
    return os.getenv("REQUIRE_PLATFORM_PAYMENT_FOR_AI", "").lower() in (
        "1",
        "true",
        "yes",
    )


def create_ai_generation_payment_intent(*, user_id: str) -> dict:
    amount_cents = DEFAULT_AMOUNT_CENTS
    if amount_cents <= 0:
        return {"error": "STRIPE_AI_GENERATION_AMOUNT_CENTS must be > 0"}

    if not STRIPE_SECRET:
        fake = f"pi_ai_{uuid.uuid4().hex}"
        return {
            "clientSecret": f"{fake}_secret_{uuid.uuid4().hex}",
            "paymentIntentId": fake,
            "amount_cents": amount_cents,
            "dev_mode": True,
        }

    stripe.api_key = STRIPE_SECRET
    pi = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=CURRENCY,
        metadata={
            "purpose": "ai_generation",
            "user_id": str(user_id),
        },
        idempotency_key=f"ai-gen-{user_id}-{uuid.uuid4().hex}"[:255],
        automatic_payment_methods={"enabled": True},
    )
    return {
        "clientSecret": pi.client_secret,
        "paymentIntentId": pi.id,
        "amount_cents": amount_cents,
    }


def verify_ai_generation_payment(*, payment_intent_id: str, user_id: str) -> str | None:
    """Returns None if OK, else error message."""
    if not payment_intent_id:
        return "platform_payment_intent_id required"
    if not STRIPE_SECRET:
        if payment_intent_id.startswith("pi_ai_"):
            return None
        return "invalid payment intent (dev mode)"
    stripe.api_key = STRIPE_SECRET
    try:
        pi = stripe.PaymentIntent.retrieve(payment_intent_id)
    except Exception as e:
        return f"could not verify payment: {e}"
    if pi.status != "succeeded":
        return "payment has not completed"
    meta = pi.metadata or {}
    if meta.get("purpose") != "ai_generation":
        return "payment intent is not for AI generation"
    if str(meta.get("user_id") or "") != str(user_id):
        return "payment intent does not match user"
    return None
