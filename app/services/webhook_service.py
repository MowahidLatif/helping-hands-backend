import os
import json
from typing import Tuple, Any
from app.models.donation import (
    get_donation_by_pi,
    set_status_by_pi,
    attach_pi_to_donation,
    set_status_by_id,
    get_donation,
)
from app.models.campaign import recompute_total_raised

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


def _extract_event(payload: bytes, sig_header: str | None) -> Tuple[str, dict]:
    """
    Returns (event_type, obj_dict). If STRIPE_WEBHOOK_SECRET is set, verifies signature.
    """
    if STRIPE_WEBHOOK_SECRET:
        import stripe

        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header or "",
                secret=STRIPE_WEBHOOK_SECRET,
            )
        except Exception as e:
            raise ValueError(f"signature verification failed: {e}")
        return event["type"], event["data"]["object"]
    # dev mode: plain JSON
    data = json.loads(payload.decode("utf-8") or "{}")
    return (
        data.get("type", ""),
        (data.get("data", {}) or {}).get("object", {}) or data,
    )  # allow raw PI


def process_stripe_event(
    payload: bytes, sig_header: str | None
) -> Tuple[int, dict[str, Any]]:
    """
    Handle selected Stripe events idempotently.
    """
    ev_type, obj = _extract_event(payload, sig_header)

    # Only handling intents for now; easy to extend later.
    if ev_type in (
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    ):
        pi_id = obj.get("id")
        metadata = obj.get("metadata", {}) or {}
        donation_id = metadata.get("donation_id")
        campaign_id = metadata.get("campaign_id")

        # ensure donation row is linked to this PI
        if donation_id:
            # idempotent: attach if not set
            d = get_donation(donation_id)
            if d and not d.get("stripe_payment_intent_id"):
                attach_pi_to_donation(donation_id, pi_id)

        # derive status
        new_status = (
            "succeeded"
            if ev_type == "payment_intent.succeeded"
            else "canceled" if ev_type == "payment_intent.canceled" else "failed"
        )

        # update by PI if present, else by donation_id
        d = get_donation_by_pi(pi_id)
        if not d and donation_id:
            set_status_by_id(donation_id, new_status)
            d = get_donation(donation_id)
        elif d:
            # idempotent write
            set_status_by_pi(pi_id, new_status)

        # recompute campaign total if we know the campaign
        if (d and d.get("campaign_id")) or campaign_id:
            recompute_total_raised(d["campaign_id"] if d else campaign_id)

        return 200, {"ok": True}

    # Ignore unhandled events
    return 200, {"ignored": ev_type or "unknown"}
