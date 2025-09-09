import os
import json
from typing import Tuple, Dict, Any
from app.models.donation import (
    get_donation_by_pi,
    set_status_by_pi,
    attach_pi_to_donation,
    set_status_by_id,
    get_donation,
)
from app.models.campaign import recompute_total_raised
from app.utils.cache import r
from app.realtime import socketio

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


def _mask_email(e: str | None) -> str | None:
    if not e:
        return None
    local, _, domain = e.partition("@")
    if not domain:
        return e
    if len(local) <= 2:
        masked = local[0:1] + "***"
    else:
        masked = local[0] + "***" + local[-1]
    return masked + "@" + domain


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
) -> Tuple[int, Dict[str, Any]]:
    """
    Handle selected Stripe events idempotently.
    """
    ev_type, obj = _extract_event(payload, sig_header)

    # Only handling PaymentIntent events for now
    if ev_type in (
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    ):
        obj = obj or {}
        pi_id = obj.get("id")
        metadata = obj.get("metadata") or {}
        donation_id = metadata.get("donation_id")
        campaign_id = metadata.get("campaign_id")

        # If we know the donation id, ensure the PI is attached (idempotent)
        if donation_id:
            d = get_donation(donation_id)
            if d and not d.get("stripe_payment_intent_id") and pi_id:
                attach_pi_to_donation(donation_id, pi_id)

        # Map Stripe event -> our status
        new_status = (
            "succeeded"
            if ev_type == "payment_intent.succeeded"
            else "canceled" if ev_type == "payment_intent.canceled" else "failed"
        )

        # Prefer updating by PI; fall back to donation_id
        d = get_donation_by_pi(pi_id) if pi_id else None
        if d and pi_id:
            set_status_by_pi(pi_id, new_status)
        elif donation_id:
            set_status_by_id(donation_id, new_status)
            d = get_donation(donation_id)  # refresh

        # Recompute totals and emit to the campaign room if we know the campaign
        cid = (d or {}).get("campaign_id") or campaign_id
        if cid:
            totals = recompute_total_raised(cid)  # {"total_raised": Decimal}
            # Bust the cached progress
            try:
                r().delete(f"campaign:{cid}:progress:v1")
            except Exception:
                pass

            # On success, broadcast a sanitized donation event
            if new_status == "succeeded":
                amount_cents = int((d or {}).get("amount_cents") or 0)
                donor_email = (d or {}).get("donor_email")
                payload_out = {
                    "campaign_id": cid,
                    "amount_cents": amount_cents,
                    "amount": round(amount_cents / 100.0, 2),
                    "donor": _mask_email(donor_email),
                    "total_raised": float(totals["total_raised"]),
                    "currency": (d or {}).get("currency", "usd"),
                }
                try:
                    socketio.emit("donation", payload_out, to=f"campaign:{cid}")
                except Exception:
                    # never fail the webhook because of a broadcast error
                    pass

        return 200, {"ok": True}

    # Ignore other event types
    return 200, {"ignored": ev_type or "unknown"}
