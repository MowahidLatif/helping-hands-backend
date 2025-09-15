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
from app.models.stripe_event import mark_event_processed
from app.services.email_service import ensure_receipt_for_donation

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
DEV_SKIP = os.getenv("DEV_STRIPE_NO_VERIFY") == "1"


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


def _extract_event(
    payload: bytes, sig_header: str | None
) -> tuple[str | None, dict | None, dict]:
    """
    Return (event_type, data.object, raw_event_dict).

    - If STRIPE_WEBHOOK_SECRET is set and DEV_STRIPE_NO_VERIFY != 1, verify the signature.
    - Otherwise (dev mode), parse the JSON payload as-is.
    """
    # Real Stripe (verify unless DEV_SKIP)
    if STRIPE_WEBHOOK_SECRET and not DEV_SKIP:
        import stripe

        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header or "",
            secret=STRIPE_WEBHOOK_SECRET,
        )
        # Convert to a plain dict we can store in jsonb
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        ev_type = event_dict.get("type")
        obj = (event_dict.get("data") or {}).get("object") or {}
        return ev_type, obj, event_dict

    # Dev path (no verify): accept your test JSON (either full event or bare object)
    try:
        raw = json.loads(payload.decode("utf-8") or "{}")
    except Exception:
        raw = {}

    if isinstance(raw, dict) and "type" in raw and "data" in raw:
        # Looks like a full Stripe-like event
        ev_type = raw.get("type")
        obj = (raw.get("data") or {}).get("object") or {}
        return ev_type, obj, raw

    # Looks like a bare PaymentIntent object; wrap it into an event-shaped dict
    wrapped = {"type": raw.get("type") or "", "data": {"object": raw}}
    ev_type = wrapped["type"]
    obj = raw
    return ev_type, obj, wrapped


def process_stripe_event(
    payload: bytes, sig_header: str | None
) -> Tuple[int, Dict[str, Any]]:
    """
    Handle selected Stripe events idempotently.
    """
    ev_type, obj, raw_event = _extract_event(payload, sig_header)

    # ---- DEDUPE (matches stripe_events schema: event_id/type/raw) ----------
    # In prod you'd use raw_event["id"]; in dev synthesize a stable key.
    pi_id = (obj or {}).get("id")
    donation_id = ((obj or {}).get("metadata") or {}).get("donation_id")
    event_id = (raw_event or {}).get(
        "id"
    ) or f"dev:{ev_type}:{pi_id or 'nopi'}:{donation_id or 'nodon'}"

    try:
        inserted = mark_event_processed(event_id, ev_type or "unknown", raw_event or {})
    except Exception as e:
        # Make noise in dev but don't crash the server
        print("[webhook error]", str(e))
        return 400, {"error": "bad payload"}

    if not inserted:
        # Duplicate (Stripe retry) -> consider it a no-op success
        return 200, {"ok": True, "duplicate": True}

    # ---- BUSINESS LOGIC -----------------------------------------------------
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
        d = None
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
        d_by_pi = get_donation_by_pi(pi_id) if pi_id else None
        if d_by_pi and pi_id:
            set_status_by_pi(pi_id, new_status)
            d = d_by_pi
        elif donation_id:
            set_status_by_id(donation_id, new_status)
            d = get_donation(donation_id)  # refresh

        # On success, create/send a receipt (idempotent inside the service)
        if new_status == "succeeded":
            try:
                ensure_receipt_for_donation((d or {}).get("id") or donation_id)
            except Exception as e:
                # Never fail the webhook because of email issues
                print("[email receipt error]", str(e))

        # Recompute totals and emit to the campaign room if we know the campaign
        cid = (d or {}).get("campaign_id") or campaign_id
        if cid:
            totals = recompute_total_raised(cid)  # {"total_raised": Decimal}
            # Bust cached progress
            try:
                r().delete(f"campaign:{cid}:progress:v1")
            except Exception:
                pass

            # Broadcast a sanitized donation event on success
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
                    # don't fail webhook on broadcast errors
                    pass

        return 200, {"ok": True}

    # Ignore other event types for now
    return 200, {"ignored": ev_type or "unknown"}
